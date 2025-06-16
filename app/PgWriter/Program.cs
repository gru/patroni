// See https://aka.ms/new-console-template for more information

using System.Data;
using System.Text.Json;
using Bogus;
using Npgsql;
using NpgsqlTypes;

public static class Program
{
    public static async Task<int> Main()
    {
        var connectionString = Environment.GetEnvironmentVariable("CONNECTION_STRING");
        if (string.IsNullOrWhiteSpace(connectionString))
            return -1;

        var writeToOutbox = Environment.GetEnvironmentVariable("OUTBOX");
        var custom = Environment.GetEnvironmentVariable("CUSTOM");
        var customQuery = Environment.GetEnvironmentVariable("CUSTOM_QUERY");
        
        await using var connection = new NpgsqlConnection(connectionString);

        while (connection.State == ConnectionState.Closed)
        {
            try
            {
                Console.WriteLine("Connecting...");
        
                await connection.OpenAsync();
            }
            catch
            {
                Console.WriteLine("Unable to connect");

                await Task.Delay(TimeSpan.FromSeconds(5));
            }
        }

        if (bool.TryParse(writeToOutbox, out var writeToOutboxValue) && writeToOutboxValue)
        {
            await WriteToOutboxTable(connection);
        }
        else if (bool.TryParse(custom, out var customValue) && customValue)
        {
            if (string.IsNullOrWhiteSpace(customQuery))
                throw new Exception("CUSTOM_QUERY is empty");

            await ExecuteCustomQuery(connection, customQuery);
        }
        else
        {
            await WriteToDebeziumTable(connection);
        }

        return 0;
    }

    private static async Task ExecuteCustomQuery(NpgsqlConnection connection, string query)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = query;

        var executeCount = 0;
        while (true)
        {
            try
            {
                await command.ExecuteNonQueryAsync();
                if (executeCount++ % 100 == 0)
                    Console.WriteLine($"Executed {executeCount} times");
            }
            catch
            {
                Console.WriteLine("Unable to execute query");

                await Task.Delay(TimeSpan.FromSeconds(1));

                if (connection.State == ConnectionState.Closed)
                {
                    try
                    {
                        await connection.OpenAsync();
                    }
                    catch
                    {
                        Console.WriteLine("Unable to restore connection");
                    }
                }
            }
        }   
    }
    
    private static async Task WriteToDebeziumTable(NpgsqlConnection connection)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = @"
INSERT INTO public.debezium_table(id, current_value) 
VALUES (1, 1)
ON CONFLICT (id) DO UPDATE 
SET current_value = public.debezium_table.current_value + 1
RETURNING current_value;";

        while (true)
        {
            try
            {
                var value = (long) command.ExecuteScalar();
                if (value++ % 100 == 0)
                    Console.WriteLine($"Value: {value}");
            }
            catch
            {
                Console.WriteLine("Unable to update value");

                await Task.Delay(TimeSpan.FromSeconds(1));

                if (connection.State == ConnectionState.Closed)
                {
                    try
                    {
                        await connection.OpenAsync();
                    }
                    catch
                    {
                        Console.WriteLine("Unable to restore connection");
                    }
                }
            }
        }   
    }
    
    private static async Task WriteToOutboxTable(NpgsqlConnection connection)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = @"
INSERT INTO public.outbox(aggregatetype, aggregateid, type, payload) 
VALUES (@aggregatetype, @aggregateid, @type, @payload);";

        var aggregateType = command.CreateParameter();
        aggregateType.ParameterName = "@aggregatetype";
        aggregateType.Value = "Person";
        command.Parameters.Add(aggregateType);
        
        var aggregateId = command.CreateParameter();
        aggregateId.ParameterName = "@aggregateid";
        command.Parameters.Add(aggregateId);
        
        var type = command.CreateParameter();
        type.ParameterName = "@type";
        type.Value = "PersonCreated";
        command.Parameters.Add(type);
        
        var payload = command.CreateParameter();
        payload.ParameterName = "@payload";
        payload.NpgsqlDbType = NpgsqlDbType.Jsonb;
        command.Parameters.Add(payload);
        
        var faker = new Faker<Payload>()
            .RuleFor(c => c.Name, f => f.Person.FullName);
        
        var rowCount = 0;
        while (true)
        {
            try
            {
                var value = faker.Generate();
                aggregateId.Value = Guid.NewGuid().ToString();
                payload.Value = JsonSerializer.SerializeToDocument(value);
                
                command.ExecuteNonQuery();
                
                if (rowCount++ % 100 == 0)
                    Console.WriteLine($"Outbox event count: {rowCount}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Unable to create outbox event: {ex.Message}");

                await Task.Delay(TimeSpan.FromSeconds(1));

                if (connection.State == ConnectionState.Closed)
                {
                    try
                    {
                        await connection.OpenAsync();
                    }
                    catch
                    {
                        Console.WriteLine("Unable to restore connection");
                    }
                }
            }
        }   
    }

    private class Payload
    {
        public string Name { get; set; }
    }
}

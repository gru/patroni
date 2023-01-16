// See https://aka.ms/new-console-template for more information

using System.Data;
using Npgsql;

var connectionString = Environment.GetEnvironmentVariable("CONNECTION_STRING");
if (string.IsNullOrWhiteSpace(connectionString))
    return -1;

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
        if (value % 100 == 0)
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

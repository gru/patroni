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
SELECT current_value FROM public.debezium_table;";

while (true)
{
    try
    {
        var value = (long?) command.ExecuteScalar();
        Console.WriteLine($"Current Value: {value}");

        await Task.Delay(TimeSpan.FromSeconds(5));
    }
    catch
    {
        Console.WriteLine("Unable to read value");

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

FROM mcr.microsoft.com/dotnet/runtime:6.0 AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /src
COPY ["PgWriter/PgWriter.csproj", "PgWriter/"]
RUN dotnet restore "PgWriter/PgWriter.csproj"
COPY . .
WORKDIR "/src/PgWriter"
RUN dotnet build "PgWriter.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "PgWriter.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "PgWriter.dll"]

FROM mcr.microsoft.com/dotnet/runtime:6.0 AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/sdk:6.0 AS build
WORKDIR /src
COPY ["PgReader/PgReader.csproj", "PgReader/"]
RUN dotnet restore "PgReader/PgReader.csproj"
COPY . .
WORKDIR "/src/PgReader"
RUN dotnet build "PgReader.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "PgReader.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "PgReader.dll"]

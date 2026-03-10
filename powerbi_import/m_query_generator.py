"""
M query (Power Query) generator from converted datasources
Generates realistic M queries instead of empty tables
"""


def generate_m_query_from_datasource(datasource, table_name):
    """
    Generate an M Power Query from a datasource
    
    Args:
        datasource: Datasource converted from source data
        table_name: Name of the table to generate
    
    Returns:
        String: Complete M query
    """
    
    connection = datasource.get('dataSource', {})
    conn_type = connection.get('connectionType', 'Unknown').lower()
    
    # Generate query based on connection type
    if 'sql' in conn_type or 'postgres' in conn_type or 'mysql' in conn_type or 'oracle' in conn_type:
        return generate_sql_query(connection, table_name)
    elif 'excel' in conn_type:
        return generate_excel_query(connection, table_name)
    elif 'csv' in conn_type or 'text' in conn_type:
        return generate_csv_query(connection, table_name)
    elif 'web' in conn_type:
        return generate_web_query(connection, table_name)
    elif 'json' in conn_type:
        return generate_json_query(connection, table_name)
    else:
        # Fallback: sample table with test data
        return generate_sample_data_query(table_name, datasource)


def generate_sql_query(connection, table_name):
    """Generate an M query for a SQL connection"""
    
    server = connection.get('connectionDetails', {}).get('server', 'YourServer')
    database = connection.get('connectionDetails', {}).get('database', 'YourDatabase')
    
    query = f"""let
    // ============================================================
    // CONFIGURATION: Update these values with your information
    // ============================================================
    Server = "{server}",
    Database = "{database}",
    TableName = "{table_name}",
    
    // ============================================================
    // DATABASE CONNECTION
    // ============================================================
    Source = Sql.Database(Server, Database),
    
    // ============================================================
    // TABLE SELECTION
    // ============================================================
    Table = Source{{[Schema="dbo", Item=TableName]}}[Data],
    
    // ============================================================
    // COLUMN TYPING (optional - adjust as needed)
    // ============================================================
    // ChangedType = Table.TransformColumnTypes(Table,{{
    //     {{"Column1", type text}},
    //     {{"Column2", type number}}
    // }}),
    
    Result = Table
in
    Result"""
    
    return query


def generate_excel_query(connection, table_name):
    """Generate an M query for an Excel file"""
    
    query = f"""let
    // ============================================================
    // CONFIGURATION: Update the Excel file path
    // ============================================================
    FilePath = "C:\\\\Data\\\\YourFile.xlsx",
    SheetName = "{table_name}",
    
    // ============================================================
    // LOADING THE EXCEL FILE
    // ============================================================
    Source = Excel.Workbook(File.Contents(FilePath), null, true),
    
    // ============================================================
    // SHEET SELECTION
    // ============================================================
    Sheet = Source{{[Item=SheetName,Kind="Sheet"]}}[Data],
    
    // ============================================================
    // HEADER PROMOTION
    // ============================================================
    PromotedHeaders = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),
    
    // ============================================================
    // AUTOMATIC COLUMN TYPING
    // ============================================================
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, List.Transform(Table.ColumnNames(PromotedHeaders), each {{_, type text}})),
    
    Result = ChangedType
in
    Result"""
    
    return query


def generate_csv_query(connection, table_name):
    """Generate an M query for a CSV file"""
    
    query = f"""let
    // ============================================================
    // CONFIGURATION: Update the CSV file path
    // ============================================================
    FilePath = "C:\\\\Data\\\\{table_name}.csv",
    
    // ============================================================
    // LOADING THE CSV FILE
    // ============================================================
    Source = Csv.Document(File.Contents(FilePath), [
        Delimiter=",", 
        Columns=null, 
        Encoding=65001,  // UTF-8
        QuoteStyle=QuoteStyle.Csv
    ]),
    
    // ============================================================
    // HEADER PROMOTION
    // ============================================================
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    
    // ============================================================
    // AUTOMATIC COLUMN TYPING
    // ============================================================
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, List.Transform(Table.ColumnNames(PromotedHeaders), each {{_, type text}})),
    
    Result = ChangedType
in
    Result"""
    
    return query


def generate_web_query(connection, table_name):
    """Generate an M query for a Web source"""
    
    query = f"""let
    // ============================================================
    // CONFIGURATION: Update the URL
    // ============================================================
    Url = "https://api.example.com/data",
    
    // ============================================================
    // WEB SOURCE CONNECTION
    // ============================================================
    Source = Json.Document(Web.Contents(Url)),
    
    // ============================================================
    // CONVERT TO TABLE
    // ============================================================
    Table = Table.FromRecords(Source),
    
    Result = Table
in
    Result"""
    
    return query


def generate_json_query(connection, table_name):
    """Generate an M query for a JSON file"""
    
    query = f"""let
    // ============================================================
    // CONFIGURATION: Update the JSON file path
    // ============================================================
    FilePath = "C:\\\\Data\\\\{table_name}.json",
    
    // ============================================================
    // LOADING THE JSON FILE
    // ============================================================
    Source = Json.Document(File.Contents(FilePath)),
    
    // ============================================================
    // CONVERT TO TABLE
    // ============================================================
    Table = if Value.Is(Source, type list) 
            then Table.FromRecords(Source)
            else Table.FromRecords({{Source}}),
    
    Result = Table
in
    Result"""
    
    return query


def generate_sample_data_query(table_name, datasource):
    """Generate an M query with sample data"""
    
    # Extract columns from the datasource
    tables = datasource.get('tables', [])
    columns = []
    
    for table in tables:
        if table.get('name') == table_name:
            columns = [col.get('name', f'Column{i}') for i, col in enumerate(table.get('columns', []), 1)]
            break
    
    # If no columns found, use default columns
    if not columns:
        columns = ['ID', 'Name', 'Category', 'Value', 'Date']
    
    column_list = ', '.join([f'"{col}"' for col in columns])
    
    # Generate sample data
    sample_rows = []
    for i in range(1, 6):  # 5 sample rows
        row_values = []
        for col in columns:
            col_lower = col.lower()
            if 'id' in col_lower:
                row_values.append(f'{i}')
            elif 'name' in col_lower:
                row_values.append(f'"Item {i}"')
            elif 'category' in col_lower or 'type' in col_lower:
                row_values.append(f'"Category {(i % 3) + 1}"')
            elif 'value' in col_lower or 'amount' in col_lower or 'price' in col_lower:
                row_values.append(f'{100 * i}')
            elif 'date' in col_lower:
                row_values.append(f'#date(2024, {i}, 15)')
            else:
                row_values.append(f'"Value {i}"')
        
        sample_rows.append('{' + ', '.join(row_values) + '}')
    
    rows_data = ',\n        '.join(sample_rows)
    
    query = f"""let
    // ============================================================
    // SAMPLE DATA FOR "{table_name}"
    // ============================================================
    // TODO: Replace with your actual data source
    // ============================================================
    
    Source = #table(
        // Column definition
        {{{column_list}}},
        
        // Sample data (5 rows)
        {{
        {rows_data}
        }}
    ),
    
    // ============================================================
    // To connect an actual data source, replace with:
    // ============================================================
    // SQL Server:
    //   Source = Sql.Database("ServerName", "DatabaseName"){{[Schema="dbo", Item="{table_name}"]}}[Data]
    //
    // Excel:
    //   Source = Excel.Workbook(File.Contents("C:\\Path\\File.xlsx"), null, true){{[Item="{table_name}"]}}[Data]
    //
    // CSV:
    //   Source = Csv.Document(File.Contents("C:\\Path\\{table_name}.csv"), [Delimiter=",", Encoding=65001])
    // ============================================================
    
    Result = Source
in
    Result"""
    
    return query


def get_column_type_mapping():
    """Return the source → M column type mapping"""
    return {
        'string': 'type text',
        'integer': 'Int64.Type',
        'real': 'type number',
        'decimal': 'type number',
        'boolean': 'type logical',
        'date': 'type date',
        'datetime': 'type datetime',
        'time': 'type time',
        'spatial': 'type text'  # Geography stored as text
    }

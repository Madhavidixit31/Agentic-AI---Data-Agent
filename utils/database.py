import psycopg2

class DatabaseUtil:

    def __init__(self, db_config):
        self.db_config = db_config
        try:
            self.connection = psycopg2.connect(**db_config)
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.connection = None

    def schema_details(self, schema_name):
        """
        Get details of the specified schema.

        Args:
            schema_name (str): The name of the schema.

        Returns:
            list: A list of tables in the schema.
        """
        
        schema_info_context = ""

        connection = self.connection
        cursor = connection.cursor()

        schema_info_context = f"Database Schema: {schema_name}\n"

        try:   

            cursor.execute("select table_name from information_schema.tables where table_schema = %s", (schema_name,))
            tables_list = cursor.fetchall()


            for table in tables_list:
                table_name = table[0]
                schema_info_context = f"{schema_info_context}\nTable: {table_name}\n"

                #add columns and data types for each table

                cursor.execute("select column_name, data_type from information_schema.columns where table_name = %s", (table_name,))
                columns_list = cursor.fetchall()

                for column in columns_list:
                    column_name = column[0]
                    data_type = column[1]
                    schema_info_context = f"{schema_info_context} Column: {column_name}, Data Type: {data_type}\n"

                #Adding Sample Data for each table
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5")
                sample_data = cursor.fetchall()
                schema_info_context = f"{schema_info_context} Sample Data:\n"
                for row in sample_data:
                    schema_info_context = f"{schema_info_context} {row}\n"

            
        
        except Exception as e:
            print(f"Error fetching schema details: {e}")
            schema_info_context = f"Error fetching schema details: {e}"
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        return schema_info_context
    
    def execute_sql(self, query):
        """
        Execute a SQL query and return the result.

        Args:
            query (str): The SQL query to execute."""

        try:
            connection = self.connection
            cursor = connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            connection.commit()
            return str(result)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
obj = DatabaseUtil({
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'Database2026@',
    'host': 'localhost',
    'port': '5432'
})

result = obj.schema_details('public')

with open("text_schema_details.txt", "w") as f:
    f.write(result)
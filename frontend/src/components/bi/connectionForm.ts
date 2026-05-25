export interface ConnectionFormState {
  db_type: string
  host: string
  port: number | null
  username: string
  password: string
  database: string
}

const DEFAULT_PORTS: Record<string, number> = {
  mysql: 3306,
  postgresql: 5432,
  doris: 9030,
  clickhouse: 8123,
  sqlserver: 1433,
  oracle: 1521,
}

export function emptyConnectionForm(dbType = 'mysql'): ConnectionFormState {
  return {
    db_type: dbType,
    host: '127.0.0.1',
    port: DEFAULT_PORTS[dbType] ?? 3306,
    username: '',
    password: '',
    database: '',
  }
}

export const CONNECTION_DEFAULT_PORTS = DEFAULT_PORTS

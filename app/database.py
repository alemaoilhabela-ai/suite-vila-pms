import os
from supabase import create_client

def get_client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )

SCHEMA = """
create table if not exists reservas (
    id bigserial primary key,
    uid text unique,
    numero_reserva text,
    hospede text,
    check_in date not null,
    check_out date not null,
    diarias int generated always as (check_out - check_in) stored,
    valor_total numeric(10,2),
    adr numeric(10,2) generated always as (
        case when (check_out - check_in) > 0
        then valor_total / (check_out - check_in)
        else 0 end
    ) stored,
    canal text check (canal in ('Booking','Airbnb','Direta','Vrbo','Bloqueio','No Show')),
    status text default 'Reserva Confirmada',
    observacoes text,
    aguardando_detalhes boolean default false,
    criado_em timestamptz default now(),
    atualizado_em timestamptz default now()
);

create table if not exists mensagens_pendentes (
    id bigserial primary key,
    uid text,
    canal text,
    check_in date,
    check_out date,
    respondido boolean default false,
    criado_em timestamptz default now()
);
"""

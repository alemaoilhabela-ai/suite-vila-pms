-- Execute este SQL no editor do Supabase (SQL Editor → New query)

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

-- Atualiza atualizado_em automaticamente
create or replace function update_atualizado_em()
returns trigger as $$
begin
  new.atualizado_em = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_reservas_atualizado
before update on reservas
for each row execute function update_atualizado_em();

-- Habilita RLS (Row Level Security) - acesso público de leitura bloqueado
alter table reservas enable row level security;
alter table mensagens_pendentes enable row level security;

-- Apenas service_role tem acesso total (usado pelo backend)
create policy "service_role full access reservas"
on reservas for all
to service_role
using (true)
with check (true);

create policy "service_role full access mensagens"
on mensagens_pendentes for all
to service_role
using (true)
with check (true);

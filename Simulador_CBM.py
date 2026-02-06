import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador CBM", layout="wide")

# --- INÍCIO DO APP (SEM SENHA) ---
st.title("🎖️ Simulador de Promoções CBM")
st.markdown("---")

# 1. CARGA DE DADOS
try:
    # O arquivo 'militares.xlsx' deve estar na raiz do seu repositório no GitHub
    df_origem = pd.read_excel('militares.xlsx')
except Exception as e:
    st.error(f"Erro: Arquivo 'militares.xlsx' não encontrado no repositório. {e}")
    st.stop()

# Sidebar para Inputs (Entradas do Usuário)
st.sidebar.header("Parâmetros da Simulação")
matricula_foco = st.sidebar.number_input("Informe a Matrícula foco:", step=1, value=12345)
data_alvo_dt = st.sidebar.date_input("Selecione a data alvo:", value=datetime(2030, 12, 31))
data_alvo = pd.to_datetime(data_alvo_dt)

if st.sidebar.button("Iniciar Simulação"):
    # Cópia do DataFrame para manter o original intacto
    df = df_origem.copy()
    
    # Formatação e Conversão
    df['Matricula'] = pd.to_numeric(df['Matricula'])
    df['Pos_Hierarquica'] = pd.to_numeric(df['Pos_Hierarquica'])
    df['Ultima_promocao'] = pd.to_datetime(df['Ultima_promocao'], dayfirst=True)
    df['Data_Admissao'] = pd.to_datetime(df['Data_Admissao'], dayfirst=True)
    df['Data_Nascimento'] = pd.to_datetime(df['Data_Nascimento'], dayfirst=True)
    df['Excedente'] = ""

    # Definição das Regras
    hierarquia = ['SD 1', 'CB', '3º SGT', '2º SGT', '1º SGT', 'SUB TEN', '2º TEN', '1º TEN', 'CAP', 'MAJ', 'TEN CEL', 'CEL']
    vagas_limite = {'SD 1': 600, 'CB': 600, '3º SGT': 573, '2º SGT': 409, '1º SGT': 245, 'SUB TEN': 96, '2º TEN': 34, '1º TEN': 29, 'CAP': 24, 'MAJ': 10, 'TEN CEL': 1, 'CEL': 9999}
    tempo_minimo = {'SD 1': 5, 'CB': 3, '3º SGT': 3, '2º SGT': 3, '1º SGT': 2, 'SUB TEN': 2, '2º TEN': 3, '1º TEN': 3, 'CAP': 3, 'MAJ': 3, 'TEN CEL': 30}
    postos_com_excedente = ['CB', '3º SGT', '2º SGT', '2º TEN', '1º TEN', 'CAP']

    data_atual = pd.to_datetime(datetime.now().strftime('%d/%m/%Y'), dayfirst=True)
    
    # Gerar datas de ciclo (26/06 e 29/11)
    datas_ciclo = []
    for ano in range(data_atual.year, data_alvo.year + 1):
        for mes, dia in [(6, 26), (11, 29)]:
            d = pd.Timestamp(year=ano, month=mes, day=dia)
            if data_atual <= d <= data_alvo:
                datas_ciclo.append(d)
    datas_ciclo.sort()

    historico_foco = []
    df_inativos = pd.DataFrame()

    # 3. LOOP CRONOLÓGICO DE SIMULAÇÃO
    progress_bar = st.progress(0)
    for idx_ciclo, data_referencia in enumerate(datas_ciclo):
        
        # A) PROMOÇÕES
        for i in range(len(hierarquia) - 2, -1, -1):
            posto_atual = hierarquia[i]
            proximo_posto = hierarquia[i+1]
            candidatos = df[df['Posto_Graduacao'] == posto_atual].sort_values('Pos_Hierarquica')
            
            for idx, militar in candidatos.iterrows():
                anos_no_posto = relativedelta(data_referencia, militar['Ultima_promocao']).years
                ocupados = len(df[(df['Posto_Graduacao'] == proximo_posto) & (df['Excedente'] != "x")])
                tem_vaga = ocupados < vagas_limite[proximo_posto]
                promoveu = False
                
                # Regra de Excedente
                if posto_atual in postos_com_excedente and anos_no_posto >= 6:
                    df.at[idx, 'Posto_Graduacao'] = proximo_posto
                    df.at[idx, 'Ultima_promocao'] = data_referencia
                    df.at[idx, 'Excedente'] = "x"
                    promoveu = True
                # Promoção Normal
                elif anos_no_posto >= tempo_minimo[posto_atual] and tem_vaga:
                    df.at[idx, 'Posto_Graduacao'] = proximo_posto
                    df.at[idx, 'Ultima_promocao'] = data_referencia
                    df.at[idx, 'Excedente'] = ""
                    promoveu = True

                if promoveu and militar['Matricula'] == matricula_foco:
                    historico_foco.append(f"📅 {data_referencia.strftime('%d/%m/%Y')}: Promovido a **{proximo_posto}**")

        # B) ABSORÇÃO DE EXCEDENTES
        for posto in hierarquia:
            ativos_normais = len(df[(df['Posto_Graduacao'] == posto) & (df['Excedente'] != "x")])
            vagas_abertas = vagas_limite.get(posto, 0) - ativos_normais
            if vagas_abertas > 0:
                excedentes = df[(df['Posto_Graduacao'] == posto) & (df['Excedente'] == "x")].sort_values('Pos_Hierarquica')
                for idx_exc in excedentes.head(int(vagas_abertas)).index:
                    df.at[idx_exc, 'Excedente'] = ""
                    if df.at[idx_exc, 'Matricula'] == matricula_foco:
                        historico_foco.append(f"✅ {data_referencia.strftime('%d/%m/%Y')}: Ocupou vaga comum em {posto}")

        # C) APOSENTADORIA
        idade = df['Data_Nascimento'].apply(lambda x: relativedelta(data_referencia, x).years)
        servico = df['Data_Admissao'].apply(lambda x: relativedelta(data_referencia, x).years)
        mask_apo = (idade >= 63) | (servico >= 35)
        
        if mask_apo.any():
            if matricula_foco in df[mask_apo]['Matricula'].values:
                historico_foco.append(f"⚠️ {data_referencia.strftime('%d/%m/%Y')}: **APOSENTADO**")
            inativos_do_ciclo = df[mask_apo].copy()
            df_inativos = pd.concat([df_inativos, inativos_do_ciclo], ignore_index=True)
            df = df[~mask_apo].copy()
        
        progress_bar.progress((idx_ciclo + 1) / len(datas_ciclo))

    # 4. EXIBIÇÃO DE RESULTADOS
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"Relatório Histórico - Matrícula {matricula_foco}")
        if not historico_foco:
            st.info("Nenhuma alteração registrada para esta matrícula no período.")
        else:
            for evento in historico_foco:
                st.write(evento)

    with col2:
        st.subheader("Status Final na Data Alvo")
        if matricula_foco in df['Matricula'].values:
            m = df[df['Matricula'] == matricula_foco].iloc[0]
            status = "EXCEDENTE" if m['Excedente'] == "x" else "ATIVO"
            st.success(f"**Posto/Graduação:** {m['Posto_Graduacao']} \n\n **Condição:** {status}")
        elif matricula_foco in df_inativos['Matricula'].values:
            m = df_inativos[df_inativos['Matricula'] == matricula_foco].iloc[0]
            st.warning(f"**Status:** APOSENTADO \n\n **Último posto:** {m['Posto_Graduacao']}")
        else:
            st.error("Matrícula não encontrada nos registos finais.")

    # 📥 BOTÕES DE DOWNLOAD
    st.markdown("---")
    st.subheader("Baixar Tabelas Finais")
    
    def converter_para_excel(df_input):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_input.to_excel(writer, index=False)
        return output.getvalue()

    c1, c2 = st.columns(2)
    c1.download_button(label="Baixar Planilha de Ativos (.xlsx)", data=converter_para_excel(df), file_name="Ativos_Simulacao.xlsx")
    c2.download_button(label="Baixar Planilha de Inativos (.xlsx)", data=converter_para_excel(df_inativos), file_name="Inativos_Simulacao.xlsx")

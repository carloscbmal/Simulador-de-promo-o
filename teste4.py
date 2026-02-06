import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io

def simulador_promocao():
    st.title("Simulador de Promoção Militar")

    # 1. Carga de Dados via Streamlit
    uploaded_file = st.file_uploader("Carregue o arquivo 'militares.xlsx'", type="xlsx")

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            return

        # Formatação (Mantida idêntica)
        df['Matricula'] = pd.to_numeric(df['Matricula'], errors='coerce')
        df['Pos_Hierarquica'] = pd.to_numeric(df['Pos_Hierarquica'], errors='coerce')
        df['Ultima_promocao'] = pd.to_datetime(df['Ultima_promocao'], dayfirst=True)
        df['Data_Admissao'] = pd.to_datetime(df['Data_Admissao'], dayfirst=True)
        df['Data_Nascimento'] = pd.to_datetime(df['Data_Nascimento'], dayfirst=True)
        df['Excedente'] = df.get('Excedente', "").fillna("") # Garante coluna vazia se não existir

        # Definição das Regras Estritas (Mantida idêntica)
        hierarquia = ['SD 1', 'CB', '3º SGT', '2º SGT', '1º SGT', 'SUB TEN', 
                      '2º TEN', '1º TEN', 'CAP', 'MAJ', 'TEN CEL', 'CEL']
        
        vagas_limite = {
            'SD 1': 600, 'CB': 600, '3º SGT': 573, '2º SGT': 409, '1º SGT': 245,
            'SUB TEN': 96, '2º TEN': 34, '1º TEN': 29, 'CAP': 24, 'MAJ': 10, 'TEN CEL': 3, 'CEL': 1
        }

        tempo_minimo = {
            'SD 1': 5, 'CB': 3, '3º SGT': 3, '2º SGT': 3, '1º SGT': 2,
            'SUB TEN': 2, '2º TEN': 3, '1º TEN': 3, 'CAP': 3, 'MAJ': 3, 'TEN CEL': 30
        }

        postos_com_excedente = ['CB', '3º SGT', '2º SGT', '2º TEN', '1º TEN', 'CAP']

        # 2. Inputs do Usuário via Streamlit
        st.sidebar.header("Parâmetros da Simulação")
        matricula_foco = st.sidebar.number_input("Informe a Matrícula Foco:", min_value=0, step=1, format="%d")
        data_alvo_input = st.sidebar.date_input("Data Alvo:", value=datetime.today() + relativedelta(years=1))
        
        botao_simular = st.sidebar.button("Executar Simulação")

        if botao_simular:
            data_alvo = pd.to_datetime(data_alvo_input)
            data_atual = pd.to_datetime(datetime.now().strftime('%d/%m/%Y'), dayfirst=True)
            
            # Gerar datas de ciclo (Mantido idêntico)
            datas_ciclo = []
            for ano in range(data_atual.year, data_alvo.year + 1):
                for mes, dia in [(6, 26), (11, 29)]:
                    d = pd.Timestamp(year=ano, month=mes, day=dia)
                    if data_atual <= d <= data_alvo:
                        datas_ciclo.append(d)
            datas_ciclo.sort()

            historico_foco = []
            df_inativos = pd.DataFrame()

            # Barra de progresso visual
            progress_bar = st.progress(0)
            status_text = st.empty()

            # 3. Loop Cronológico de Simulação (Mantido idêntico)
            total_ciclos = len(datas_ciclo)
            for idx_ciclo, data_referencia in enumerate(datas_ciclo):
                
                # Atualiza barra de progresso
                status_text.text(f"Processando data: {data_referencia.strftime('%d/%m/%Y')}")
                if total_ciclos > 0:
                    progress_bar.progress((idx_ciclo + 1) / total_ciclos)

                # A) PROMOÇÕES (Cascata: do topo para a base)
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
                            historico_foco.append(f"✅ {data_referencia.strftime('%d/%m/%Y')}: Promovido a {proximo_posto}")

                # B) ABSORÇÃO DE EXCEDENTES
                for posto in hierarquia:
                    ativos_normais = len(df[(df['Posto_Graduacao'] == posto) & (df['Excedente'] != "x")])
                    vagas_abertas = vagas_limite.get(posto, 0) - ativos_normais
                    
                    if vagas_abertas > 0:
                        excedentes = df[(df['Posto_Graduacao'] == posto) & (df['Excedente'] == "x")].sort_values('Pos_Hierarquica')
                        for idx_exc in excedentes.head(int(vagas_abertas)).index:
                            df.at[idx_exc, 'Excedente'] = ""
                            if df.at[idx_exc, 'Matricula'] == matricula_foco:
                                historico_foco.append(f"ℹ️ {data_referencia.strftime('%d/%m/%Y')}: Ocupou vaga comum em {posto}")

                # C) APOSENTADORIA
                idade = df['Data_Nascimento'].apply(lambda x: relativedelta(data_referencia, x).years)
                servico = df['Data_Admissao'].apply(lambda x: relativedelta(data_referencia, x).years)
                
                mask_apo = (idade >= 63) | (servico >= 35)
                
                if mask_apo.any():
                    if matricula_foco in df[mask_apo]['Matricula'].values:
                        historico_foco.append(f"🛑 {data_referencia.strftime('%d/%m/%Y')}: APOSENTADO")
                    
                    inativos_do_ciclo = df[mask_apo].copy()
                    df_inativos = pd.concat([df_inativos, inativos_do_ciclo], ignore_index=True)
                    df = df[~mask_apo].copy()

            # 4. Saída Final (Display e Downloads)
            st.divider()
            st.subheader(f"Relatório - Matrícula {matricula_foco}")
            
            if not historico_foco:
                st.info("Nenhuma alteração registrada para esta matrícula no período.")
            else:
                for evento in historico_foco:
                    st.write(evento)
            
            # Status Final
            status_msg = ""
            if matricula_foco in df['Matricula'].values:
                m = df[df['Matricula'] == matricula_foco].iloc[0]
                status = "EXCEDENTE" if m['Excedente'] == "x" else "ATIVO"
                status_msg = f"STATUS FINAL: {m['Posto_Graduacao']} ({status})"
                st.success(status_msg)
            elif matricula_foco in df_inativos['Matricula'].values:
                m = df_inativos[df_inativos['Matricula'] == matricula_foco].iloc[0]
                status_msg = f"STATUS FINAL: APOSENTADO (Último posto: {m['Posto_Graduacao']})"
                st.warning(status_msg)
            else:
                st.error("Matrícula não encontrada no arquivo.")

            st.divider()
            st.subheader("Downloads dos Resultados")

            # Função auxiliar para download
            def to_excel_bytes(dataframe):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    dataframe.to_excel(writer, index=False)
                return output.getvalue()

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Baixar Ativos Final (.xlsx)",
                    data=to_excel_bytes(df),
                    file_name="Ativos_Final.xlsx",
                    mime="application/vnd.ms-excel"
                )
            with col2:
                if not df_inativos.empty:
                    st.download_button(
                        label="Baixar Inativos Final (.xlsx)",
                        data=to_excel_bytes(df_inativos),
                        file_name="Inativos_Final.xlsx",
                        mime="application/vnd.ms-excel"
                    )

if __name__ == "__main__":
    simulador_promocao()

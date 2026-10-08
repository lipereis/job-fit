"""Writes eval/cases.jsonl.

Every posting here is fictional, written for this test set in the style of real ones (Portuguese and
English). Several reproduce a mistake an earlier version of the scorer made; the 'why' field says which.
The labels are one person's judgement for the profile in eval/profile.json.
"""
import json
from pathlib import Path

CASES = [
    # ---------------- apply ----------------
    ("apply-automation-junior", "Analista de Automação Júnior", "Remoto, Brasil", "apply",
     "core target: automation with the profile's own stack", """
Sobre a empresa
Somos uma startup de logística que usa IA em toda a operação.

Responsabilidades
- Criar e manter automações de processos internos com n8n
- Integrar sistemas via APIs REST e webhooks
- Escrever scripts em Python para tratar dados

Requisitos
- Python
- Experiência com n8n ou Zapier
- Consumo de APIs REST
- SQL básico
- Git

Diferenciais
- Experiência com LLMs (OpenAI, Gemini)
- Docker

Benefícios
Vale-refeição, plano de saúde.
"""),
    ("apply-ai-automation-en", "Junior AI Automation Specialist", "Remote, LATAM", "apply",
     "same role family, English posting", """
About us
We build tools for creators.

What you'll do
- Build internal workflows in n8n and Zapier
- Connect LLM APIs to our content pipeline
- Write and test prompts

Requirements
- Workflow automation experience (n8n, Zapier or Make.com)
- Working knowledge of REST APIs and webhooks
- Python scripting
- Prompt engineering with OpenAI or Claude

Nice to have
- Video editing background
- Docker
"""),
    ("apply-video-editor-rio", "Editor de Vídeo para Redes Sociais", "Rio de Janeiro, RJ (presencial)", "apply",
     "on-site, but in a city the profile accepts", """
Atividades
Edição de vídeos curtos para Reels, TikTok e Shorts, do bruto ao material final.

Requisitos
- Domínio de Premiere Pro
- Experiência com vídeos curtos para Reels e TikTok
- Noções de redes sociais

Diferenciais
- After Effects
- Roteiro
"""),
    ("apply-python-junior", "Desenvolvedor Python Júnior", "Remoto", "apply",
     "junior developer role covered by projects", """
O que você vai fazer
Desenvolver e manter serviços internos em Python.

O que esperamos
- Python
- FastAPI ou Flask
- SQL
- Git
- Testes automatizados com pytest

Diferenciais
- Docker
- Experiência com LLMs
"""),
    ("apply-content-ops", "Content Operations Analyst (AI)", "Remote, Brazil", "apply",
     "the hybrid role: video plus automation", """
The role
You will run our short-form video pipeline and automate the repetitive parts.

Requirements
- Video editing (Premiere or DaVinci Resolve)
- Short-form content for TikTok and Reels
- Workflow automation with n8n or Zapier
- Comfortable writing prompts for generative AI tools

Nice to have
- Python
- Transcription tooling such as Whisper
"""),
    ("apply-trainee-ia", "Trainee em Automação e IA", "Remoto, Brasil", "apply",
     "entry level, stack matches", """
Sua missão
Apoiar o time na construção de automações com IA generativa.

Requisitos
- Lógica de programação em Python
- Noções de APIs REST
- Git
- Interesse em IA generativa e LLMs

Diferenciais
- n8n
"""),
    ("apply-videomaker-ai", "Videomaker Júnior com foco em IA", "Rio de Janeiro, RJ (híbrido)", "apply",
     "hybrid in an accepted city", """
Responsabilidades
Editar vídeos para redes sociais e testar ferramentas de IA generativa no fluxo de edição.

Requisitos
- Edição de vídeo no Premiere ou DaVinci
- Vídeos curtos para Reels e TikTok
- Curiosidade por ferramentas de IA generativa

Diferenciais
- Motion graphics
- Transcrição com Whisper
"""),
    ("apply-support-video-saas", "Technical Support Engineer (Junior)", "Remote, Brazil", "apply",
     "borderline: support experience is missing, product knowledge is strong", """
About us
We make an online video editor.

What you'll do
Help creators solve problems with exports, captions and integrations.

Requirements
- Technical support or troubleshooting experience
- Understanding of REST APIs and webhooks
- Hands-on video editing knowledge
- English

Nice to have
- Python
- ffmpeg
"""),
    # ---------------- skip ----------------
    ("skip-collections-cs", "Analista de Customer Success 1 (Júnior - Cobrança e Retenção)", "Remoto, Brasil", "skip",
     "regression: good-looking junior title, job is debt collection; an early scorer gave this 70", """
Sobre o grupo
Somos pioneiros na aplicação de Inteligência Artificial em larga escala. Nossa plataforma digital recebe
milhões de acessos, e temos interesse em pessoas que queiram crescer com o restante do time.

Suas responsabilidades
- Atender solicitações de cancelamento e aplicar estratégias de retenção
- Realizar cobrança de clientes inadimplentes e renegociação de pendências
- Manter o Salesforce atualizado

Requisitos
- Forte experiência em retenção de clientes B2B e combate ao churn
- Experiência consistente em cobrança e gestão de inadimplência
- Conhecimento de métricas de performance e ROI
"""),
    ("skip-marketing-substrings", "Analista de Marketing Digital", "Remoto", "skip",
     "regression: 'digital' used to match Git and 'interesse'/'restante' used to match REST", """
Responsabilidades
Gestão de campanhas digitais, com interesse genuíno em resultados e apoio ao restante do time.

Requisitos
- Experiência com Google Ads e Meta Ads
- SEO
- Google Analytics
"""),
    ("skip-senior-ai-engineer", "Senior AI Engineer", "Remote, Brazil", "skip", "seniority and infrastructure gap", """
Requirements
- 5+ years of software engineering experience
- Python
- AWS and Kubernetes in production
- Microservices and distributed systems
- LLM APIs and RAG

Nice to have
- LangChain
"""),
    ("skip-java-backend", "Desenvolvedor Backend Java Pleno", "Remoto, Brasil", "skip", "different stack", """
Requisitos
- Java e Spring Boot
- Microsserviços
- Kubernetes
- AWS
- SQL
- 3 anos de experiência
"""),
    ("skip-sdr", "SDR Júnior", "Remoto", "skip", "sales role", """
Atividades
Prospecção ativa de leads por telefone e e-mail.

Requisitos
- Experiência em prospecção e cold call
- Uso de CRM (HubSpot ou Pipedrive)
- Metas comerciais
"""),
    ("skip-editor-other-city", "Editor de Vídeo", "São Paulo, SP (presencial)", "skip",
     "skills match, but on-site in a city the profile does not accept", """
Requisitos
- Premiere Pro
- Vídeos curtos para Reels e TikTok
- After Effects
"""),
    ("skip-infra-support", "Analista de Suporte N1", "Remoto", "skip", "infrastructure support", """
Requisitos
- Active Directory
- Redes de computadores
- ITIL
- Atendimento ao cliente via help desk
"""),
    ("skip-ml-engineer", "Machine Learning Engineer", "Remote, LATAM", "skip", "model training, not application work", """
Requirements
- PyTorch or TensorFlow
- Model training and fine-tuning
- MLOps
- AWS
- Python
"""),
    ("skip-finance-ai-blurb", "Assistente Financeiro", "Remoto, Brasil", "skip",
     "regression: the company blurb talks about AI, automation and Python; the job does not", """
Sobre nós
Somos uma empresa de tecnologia movida a IA generativa. Nosso time de engenharia usa Python, n8n,
APIs REST e LLMs todos os dias para automatizar processos.

Atividades
Contas a pagar, conciliação bancária e apoio ao fechamento.

Requisitos
- Experiência com contas a pagar
- Conciliação bancária
- Excel
"""),
    ("skip-senior-motion", "Motion Designer Sênior", "Remoto", "skip", "seniority", """
Requisitos
- After Effects avançado
- Motion graphics para publicidade
- 5 anos de experiência
- Illustrator e Photoshop
"""),
    ("skip-data-analyst-mid", "Analista de Dados Pleno", "Remoto, Brasil", "skip", "data stack the profile lacks", """
Requisitos
- SQL avançado
- Power BI
- ETL com Airflow
- Spark
- 3 anos de experiência
"""),
    ("skip-csm-enterprise", "Customer Success Manager, Enterprise", "Remote, Brazil", "skip", "account management", """
Requirements
- Proven track record managing enterprise renewals
- Customer retention and churn reduction
- Salesforce
- Sales experience
"""),
    ("skip-vague", "Analista de IA", "Remoto", "skip",
     "regression: attractive title with nothing concrete in the text must not pass on the title alone", """
Procuramos uma pessoa proativa, comunicativa e apaixonada por tecnologia para somar ao nosso time.
Se você gosta de desafios, venha fazer parte!
"""),
    ("skip-call-center", "Atendente de Call Center", "Remoto", "skip", "call center", """
Requisitos
- Experiência em call center ou telemarketing
- Atendimento ao cliente
"""),
    ("skip-fullstack-mid", "Full-Stack Engineer (Mid-level)", "Remote, LATAM", "skip", "level and cloud gap", """
Requirements
- 3+ years building production web apps
- React and TypeScript
- Node.js
- GraphQL
- AWS
- Kubernetes
"""),
    ("skip-rpa-uipath", "Desenvolvedor RPA Pleno", "Remoto, Brasil", "skip", "automation in name, different toolset and level", """
Requisitos
- UiPath
- SQL
- C#
- 3 anos de experiência com RPA
"""),
    # ---------------- near the cutoff ----------------
    ("hard-senior-in-body", "Data Developer (IA / Automação)", "Remoto, Brasil", "skip",
     "neutral title, but the text asks for seniority and for cloud the profile lacks", """
Sobre a vaga
Buscamos uma pessoa com senioridade técnica, que resolve problemas complexos com autonomia.

Responsabilidades
- Desenvolver aplicações e automações para curadoria e publicação de conteúdo
- Construir integrações entre plataformas e APIs

O que esperamos de você
- Python
- APIs REST
- SQL
- AWS
- Git
- Microsserviços

Diferenciais
- Experiência com OpenAI ou IA generativa
- RAG e busca semântica
- LangChain ou CrewAI
- Testes automatizados
"""),
    ("hard-half-match", "Analista de Automação Júnior (Operações)", "Remoto", "skip",
     "automation title, but half of the requirements are office tools the profile lacks", """
Requisitos
- n8n ou Power Automate
- Excel avançado
- Power BI
- Salesforce
- SQL
"""),
    ("hard-mid-video-rio", "Editor de Vídeo Pleno", "Rio de Janeiro, RJ (presencial)", "apply",
     "one level above the profile, but the skills are all there and the city fits", """
Requisitos
- Premiere Pro
- After Effects
- 3 anos de experiência com edição de vídeo
"""),
    ("hard-equal-weights", "Analista de Automação Júnior", "Remoto, Brasil", "apply",
     "known weakness: every requirement weighs the same, so two minor gaps sink a role that fits", """
Requisitos
- Automação de processos com n8n
- Excel
- SQL
- Inglês
"""),
]

rows = [{"id": cid, "title": title, "location": location, "label": label, "why": why, "description": text.strip()}
        for cid, title, location, label, why, text in CASES]
out = Path(__file__).with_name("cases.jsonl")
out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
print(len(rows), "cases ->", out.name)

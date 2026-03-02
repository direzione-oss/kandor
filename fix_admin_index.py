
import os

file_path = r"core\templates\admin\index.html"

content = """{% extends "admin/base_site.html" %}
{% load i18n static %}

{% block extrastyle %}{{ block.super }}<link rel="stylesheet" href="{% static "admin/css/dashboard.css" %}">
<style>
    /* Rimozione Colonna Modifica e Stile Pulito */
    #content-main {
        width: 100% !important;
    }
    
    /* Cards per Operazioni Veloci (SOTTO) */
    .quick-ops-container {
        display: flex;
        gap: 20px;
        margin-top: 40px;
        margin-bottom: 40px;
        flex-wrap: wrap;
        border-top: 1px solid #eee;
        padding-top: 20px;
    }
    .quick-card {
        flex: 1;
        min-width: 200px;
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        text-align: center;
        border-top: 4px solid #ccc;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .quick-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    .quick-card h3 {
        margin-top: 0;
        color: #333;
        font-size: 16px;
    }
    .quick-card p {
        color: #777;
        font-size: 13px;
    }
    .quick-card a {
        display: inline-block;
        margin-top: 10px;
        padding: 8px 20px;
        background: var(--button-bg, #E60000);
        color: white;
        text-decoration: none;
        border-radius: 4px;
        font-weight: bold;
    }
    
    /* App Box Generale */
    .app-box {
        background: white;
        margin-bottom: 20px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        overflow: hidden;
    }
    .app-box caption {
        background: #333;
        color: white;
        padding: 10px 15px;
        text-align: left;
        font-size: 16px;
        font-weight: bold;
    }
    .app-box table {
        width: 100%;
        border-collapse: collapse;
    }
    .app-box th, .app-box td {
        padding: 12px 15px;
        border-bottom: 1px solid #eee;
        text-align: left;
    }
    
    /* Colonne Split Dashboard */
    .dashboard-columns {
        display: flex;
        gap: 20px;
    }
    .dashboard-col {
        flex: 1;
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        overflow: hidden;
    }
    .dashboard-col h2 {
        background: #333;
        color: white;
        margin: 0;
        padding: 10px 15px;
        font-size: 16px;
        border-bottom: 2px solid var(--primary-color, #E60000);
    }
    
    /* Nascondi Recent Actions Sidebar */
    #content-related { display: none; }
</style>
{% endblock %}

{% block coltype %}colM{% endblock %}

{% block bodyclass %}{{ block.super }} dashboard{% endblock %}

{% block sidebar %}<!-- Sidebar rimossa -->{% endblock %}

{% block content %}
<div id="content-main">

    {% if app_list %}
        <!-- 1. APPLICAZIONI (Kandor App) - SPLIT 2 COLONNE -->
        {% for app in app_list %}
            {% if app.app_label != 'auth' and app.app_label != 'admin_interface' %}
                
                <div class="dashboard-columns">
                    <!-- COLONNA SINISTRA: Operatività -->
                    <div class="dashboard-col">
                        <h2>Operatività Giornaliera</h2>
                        <table>
                            {% for model in app.models %}
                                {% if model.object_name == 'AssegnazioneTurno' or model.object_name == 'Assenza' or model.object_name == 'TimeTracking' or model.object_name == 'Turno' %}
                                <tr>
                                    <th scope="row"><a href="{{ model.admin_url }}">{{ model.name }}</a></th>
                                    <td style="text-align: right;">
                                        {% if model.add_url %}<a href="{{ model.add_url }}" class="addlink" style="color: #999; font-size: 12px;">+ Aggiungi</a>{% endif %}
                                    </td>
                                </tr>
                                {% endif %}
                            {% endfor %}
                        </table>
                    </div>

                    <!-- COLONNA DESTRA: Risorse & Anagrafiche -->
                    <div class="dashboard-col">
                        <h2>Anagrafiche & Risorse</h2>
                        <table>
                            {% for model in app.models %}
                                {% if model.object_name == 'Cliente' or model.object_name == 'Dipendente' or model.object_name == 'Mezzo' or model.object_name == 'Qualifica' or model.object_name == 'Squadra' %}
                                <tr>
                                    <th scope="row"><a href="{{ model.admin_url }}">{{ model.name }}</a></th>
                                    <td style="text-align: right;">
                                        {% if model.add_url %}<a href="{{ model.add_url }}" class="addlink" style="color: #999; font-size: 12px;">+ Aggiungi</a>{% endif %}
                                    </td>
                                </tr>
                                {% endif %}
                            {% endfor %}
                        </table>
                    </div>
                </div>

            {% endif %}
        {% endfor %}

        <!-- 2. OPERAZIONI VELOCI (Cards) - SOTTO -->
        <h4 style="margin-top: 30px; color: #666; text-transform: uppercase;">Operazioni Frequenti</h4>
        <div class="quick-ops-container">
            <div class="quick-card" style="border-color: #417690;">
                <h3>🏥 Jolly</h3>
                <p>Trova un sostituto per un turno scoperto</p>
                <a href="{% url 'find_jolly' %}">Trova Sostituto</a>
            </div>
            <div class="quick-card" style="border-color: #79aec8;">
                <h3>📊 Report</h3>
                <p>Verifica ore lavorate vs contratto</p>
                <a href="{% url 'reconciliation' %}">Vedi Report</a>
            </div>
            <div class="quick-card" style="border-color: #669966;">
                <h3>🗓️ Turni</h3>
                <p>Genera i turni per la prossima settimana</p>
                <a href="{% url 'generate_shifts' %}">Genera Ora</a>
            </div>
            <div class="quick-card" style="border-color: #777;">
                <h3>💾 Dati</h3>
                <p>Import/Export e Backup Database</p>
                <a href="/data-management/">Gestisci</a>
            </div>
        </div>

        <!-- 3. SISTEMA (In fondo) -->
        <div style="margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
            <h4 style="color: #ccc; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; margin-bottom: 15px;">Amministrazione Sistema</h4>
            {% for app in app_list %}
                {% if app.app_label == 'auth' %}
                    <div class="app-box" style="opacity: 0.8;">
                        <table>
                            <caption>{{ app.name }}</caption>
                            {% for model in app.models %}
                                <tr>
                                    <th scope="row"><a href="{{ model.admin_url }}">{{ model.name }}</a></th>
                                    <td style="text-align: right;">
                                        {% if model.add_url %}
                                            <a href="{{ model.add_url }}" class="addlink" style="color: #999; font-size: 12px;">+ Aggiungi</a>
                                        {% endif %}
                                    </td>
                                </tr>
                            {% endfor %}
                        </table>
                    </div>
                {% endif %}
            {% endfor %}
        </div>

    {% else %}
        <p>{% translate "You don't have permission to view or edit anything." %}</p>
    {% endif %}
</div>
{% endblock %}
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
    print(f"Overwritten {file_path}")

import os

template = r'''<style>
.telegram-item {margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #eee;display:flex;align-items:start;gap:10px;transition:all .3s ease}
.telegram-item.completed-task {opacity:.5}
.telegram-item.completed-task.hidden-managed {display:none!important}
.telegram-note {font-size:.8em;color:#888;display:block;margin-top:2px}
.toggle-managed-btn {background:#f0f0f0;border:1px solid #ddd;border-radius:4px;padding:4px 10px;font-size:11px;cursor:pointer;color:#666;margin-left:auto}
.toggle-managed-btn:hover {background:#e0e0e0}
.toggle-managed-btn.active {background:#2980b9;color:#fff;border-color:#2980b9}
</style>
<div class="module dashboard-widget">
<h2 style="display:flex;justify-content:space-between;align-items:center;cursor:pointer" onclick="toggleWidget('telegram-content',this)">
<span>Telegram Feed</span><span style="font-size:14px">&#9660;</span>
</h2>
<div id="telegram-content" style="display:flex;gap:20px;flex-wrap:wrap">
<div style="flex:1;min-width:250px;background:#fff;padding:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="margin:0;color:#447e9b;flex:1">Ultime Ore</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('hours-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #447e9b;margin-bottom:10px"></div>
<ul id="hours-list" style="list-style:none;padding:0;max-height:400px;overflow-y:auto" data-hide-managed="true">
{% for item in latest_hours %}
<li class="telegram-item {% if item.is_validated %}completed-task hidden-managed{% endif %}">
<input type="checkbox" onclick="toggleStatus('timetracking',{{ item.id }},this)" {{ item.is_validated|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span style="color:#666">{{ item.assegnazione.cliente }}</span><br>
<small>{{ item.check_out|date:"d/m H:i" }} - {{ item.durata_ore|floatformat:1 }}h</small>
{% if item.note %}<em class="telegram-note">{{ item.note|truncatechars:40 }}</em>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999">Nessuna attivita recente.</li>
{% endfor %}
</ul>
</div>
<div style="flex:1;min-width:250px;background:#fff;padding:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="margin:0;color:#eca23e;flex:1">Assenze</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('absences-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #eca23e;margin-bottom:10px"></div>
<ul id="absences-list" style="list-style:none;padding:0;max-height:400px;overflow-y:auto" data-hide-managed="true">
{% for item in latest_absences %}
<li class="telegram-item {% if item.is_processed %}completed-task hidden-managed{% endif %}">
<input type="checkbox" onclick="toggleStatus('assenza',{{ item.id }},this)" {{ item.is_processed|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span style="background:#eee;padding:2px 5px;border-radius:4px;font-size:.8em">{{ item.get_tipo_display }}</span><br>
<small>Il {{ item.data_inizio|date:"d/m/Y" }}</small>
{% if item.note %}<em class="telegram-note">{{ item.note|truncatechars:40 }}</em>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999">Nessuna assenza recente.</li>
{% endfor %}
</ul>
</div>
<div style="flex:1;min-width:250px;background:#fff;padding:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="margin:0;color:#ba2121;flex:1">Segnalazioni</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('reports-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #ba2121;margin-bottom:10px"></div>
<ul id="reports-list" style="list-style:none;padding:0;max-height:400px;overflow-y:auto" data-hide-managed="true">
{% for item in latest_reports %}
<li class="telegram-item {% if item.risolto %}completed-task hidden-managed{% endif %}">
<input type="checkbox" onclick="toggleStatus('segnalazione',{{ item.id }},this)" {{ item.risolto|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span>{{ item.testo|truncatechars:50 }}</span><br>
<small>{{ item.data_inserimento|date:"d/m H:i" }}</small>
{% if item.risolto %}<span style="color:green">&#10004;</span>{% else %}<span style="color:red">&#9888;</span>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999">Nessuna segnalazione.</li>
{% endfor %}
</ul>
</div>
</div>
</div>
<script>
if(typeof toggleWidget==='undefined'){function toggleWidget(id,header){var c=document.getElementById(id);var i=header.querySelector('span:last-child');if(c.style.display==="none"){c.style.display="flex";i.innerText="\u25bc"}else{c.style.display="none";i.innerText="\u25b2"}}}
function toggleManaged(listId,btn){var ul=document.getElementById(listId);var hiding=ul.getAttribute('data-hide-managed')==='true';if(hiding){ul.setAttribute('data-hide-managed','false');ul.querySelectorAll('.completed-task').forEach(function(li){li.classList.remove('hidden-managed')});btn.textContent='Nascondi gestiti';btn.classList.add('active')}else{ul.setAttribute('data-hide-managed','true');ul.querySelectorAll('.completed-task').forEach(function(li){li.classList.add('hidden-managed')});btn.textContent='Mostra gestiti';btn.classList.remove('active')}}
function toggleStatus(model,id,checkbox){var li=checkbox.closest('li');var ul=li.closest('ul');if(checkbox.checked){li.classList.add('completed-task');if(ul.getAttribute('data-hide-managed')==='true'){setTimeout(function(){li.classList.add('hidden-managed')},300)}}else{li.classList.remove('completed-task');li.classList.remove('hidden-managed')}fetch('/telegram-toggle/'+model+'/'+id+'/',{method:'POST',headers:{'X-CSRFToken':'{{ csrf_token }}'}}).then(function(r){return r.json()}).then(function(d){if(d.status==='ok'){checkbox.checked=d.new_state;if(d.new_state){li.classList.add('completed-task');if(ul.getAttribute('data-hide-managed')==='true'){setTimeout(function(){li.classList.add('hidden-managed')},300)}}else{li.classList.remove('completed-task');li.classList.remove('hidden-managed')}}else{alert('Errore: '+d.error);checkbox.checked=!checkbox.checked}}).catch(function(e){console.error(e);alert('Errore di connessione');checkbox.checked=!checkbox.checked})}
</script>
'''

filepath = os.path.join('core', 'templates', 'admin', 'widgets', 'telegram_feed_widget.html')
with open(filepath, 'wb') as f:
    f.write(template.lstrip('\n').encode('utf-8'))
print(f'OK: {filepath}')

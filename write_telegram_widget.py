import os

template = r'''<style>
.telegram-item {margin-bottom:10px;padding:10px;border-bottom:1px solid #eee;display:flex;align-items:start;gap:10px;transition:all .3s ease}
.telegram-item.completed-task {opacity:.5}
.telegram-item.completed-task.hidden-managed {display:none!important}
.telegram-item div {word-wrap:break-word;overflow-wrap:break-word;min-width:0;flex:1}
.telegram-note {font-size:.85em;color:#888;display:block;margin-top:4px;word-wrap:break-word}
.toggle-managed-btn {background:#f0f0f0;border:1px solid #ddd;border-radius:4px;padding:4px 10px;font-size:11px;cursor:pointer;color:#666;margin-left:auto;white-space:nowrap}
.toggle-managed-btn:hover {background:#e0e0e0}
.toggle-managed-btn.active {background:#2980b9;color:#fff;border-color:#2980b9}
.tg-card {flex:1;min-width:300px;background:#fff;padding:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1)}
.tg-card h3 {margin:0;flex:1}
.tg-card ul {list-style:none;padding:0;max-height:400px;overflow-y:auto}
.tg-card strong {font-size:14px}
.tg-card span,.tg-card small {font-size:13px;line-height:1.4}
</style>
<div class="module dashboard-widget">
<h2 style="display:flex;justify-content:space-between;align-items:center;cursor:pointer" onclick="toggleWidget('telegram-content',this)">
<span>Telegram Feed</span><span style="font-size:14px">&#9660;</span>
</h2>
<div id="telegram-content" style="display:flex;gap:20px;flex-wrap:wrap">
<div class="tg-card">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="color:#447e9b">Ultime Ore</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('hours-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #447e9b;margin-bottom:10px"></div>
<ul id="hours-list" data-hide-managed="true">
{% for item in latest_hours %}
<li class="telegram-item {% if item.is_validated %}completed-task hidden-managed{% endif %}">
<input type="checkbox" style="margin-top:4px;min-width:16px" onclick="toggleStatus('timetracking',{{ item.id }},this)" {{ item.is_validated|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span style="color:#555">{{ item.assegnazione.cliente }}</span><br>
<small style="color:#888">{{ item.check_out|date:"d/m H:i" }} - {{ item.durata_ore|floatformat:1 }}h</small>
{% if item.note %}<em class="telegram-note">{{ item.note }}</em>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999;padding:10px">Nessuna attivita recente.</li>
{% endfor %}
</ul>
</div>
<div class="tg-card">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="color:#eca23e">Assenze</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('absences-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #eca23e;margin-bottom:10px"></div>
<ul id="absences-list" data-hide-managed="true">
{% for item in latest_absences %}
<li class="telegram-item {% if item.is_processed %}completed-task hidden-managed{% endif %}">
<input type="checkbox" style="margin-top:4px;min-width:16px" onclick="toggleStatus('assenza',{{ item.id }},this)" {{ item.is_processed|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span style="background:#eee;padding:2px 6px;border-radius:4px;font-size:12px">{{ item.get_tipo_display }}</span><br>
<small style="color:#888">Dal {{ item.data_inizio|date:"d/m/Y" }} al {{ item.data_fine|date:"d/m/Y" }}</small>
{% if item.note %}<em class="telegram-note">{{ item.note }}</em>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999;padding:10px">Nessuna assenza recente.</li>
{% endfor %}
</ul>
</div>
<div class="tg-card">
<div style="display:flex;align-items:center;margin-bottom:10px">
<h3 style="color:#ba2121">Segnalazioni</h3>
<button class="toggle-managed-btn" onclick="toggleManaged('reports-list',this)">Mostra gestiti</button>
</div>
<div style="border-bottom:2px solid #ba2121;margin-bottom:10px"></div>
<ul id="reports-list" data-hide-managed="true">
{% for item in latest_reports %}
<li class="telegram-item {% if item.risolto %}completed-task hidden-managed{% endif %}">
<input type="checkbox" style="margin-top:4px;min-width:16px" onclick="toggleStatus('segnalazione',{{ item.id }},this)" {{ item.risolto|yesno:"checked," }}>
<div>
<strong>{{ item.dipendente }}</strong><br>
<span style="color:#555">{{ item.testo }}</span><br>
<small style="color:#888">{{ item.data_inserimento|date:"d/m H:i" }}</small>
{% if item.risolto %}<span style="color:green"> &#10004; Risolto</span>{% else %}<span style="color:red"> &#9888; Aperta</span>{% endif %}
</div>
</li>
{% empty %}
<li style="color:#999;padding:10px">Nessuna segnalazione.</li>
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

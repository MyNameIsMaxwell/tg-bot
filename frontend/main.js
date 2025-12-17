const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  // Set header color to match iOS style
  tg.setHeaderColor('#F2F2F7');
  tg.setBackgroundColor('#F2F2F7');
}

const apiHeaders = () => ({
  'Content-Type': 'application/json',
  'X-Telegram-Init-Data': tg?.initDataUnsafe ? tg.initData : '',
});

const templatesContainer = document.getElementById('templates-container');
const dialog = document.getElementById('template-dialog');
const dialogTitle = document.getElementById('dialog-title');
const form = document.getElementById('template-form');
const sheetBackdrop = document.getElementById('sheet-backdrop');

const reloadBtn = document.getElementById('reload-btn');
const createBtn = document.getElementById('create-btn');
const cancelBtn = document.getElementById('dialog-cancel');
const saveBtn = document.getElementById('dialog-save');
const loadTargetsBtn = document.getElementById('load-targets-btn');
const targetsList = document.getElementById('targets-list');

// Show loading skeleton
function showLoading() {
  templatesContainer.innerHTML = `
    <div class="ios-skeleton ios-skeleton-item"></div>
    <div class="ios-skeleton ios-skeleton-item"></div>
    <div class="ios-skeleton ios-skeleton-item"></div>
  `;
}

// Show empty state
function showEmptyState() {
  templatesContainer.innerHTML = `
    <div class="ios-empty-state">
      <div class="ios-empty-state-icon">📋</div>
      <div class="ios-empty-state-title">Нет шаблонов</div>
      <div class="ios-empty-state-text">Создайте первый шаблон для автоматических сводок</div>
    </div>
  `;
}

async function loadTemplates() {
  showLoading();
  try {
    const response = await fetch('/api/templates/', {
      headers: apiHeaders(),
    });
    if (!response.ok) {
      throw new Error('Failed to load templates');
    }
    const templates = await response.json();
    renderTemplates(templates);
  } catch (error) {
    templatesContainer.innerHTML = `
      <div class="ios-empty-state">
        <div class="ios-empty-state-icon">⚠️</div>
        <div class="ios-empty-state-title">Ошибка загрузки</div>
        <div class="ios-empty-state-text">${error.message}</div>
      </div>
    `;
  }
}

function renderTemplates(templates) {
  if (!templates.length) {
    showEmptyState();
    return;
  }

  templatesContainer.innerHTML = '';
  templates.forEach((tpl) => {
    const card = document.createElement('div');
    card.className = 'ios-template-detail';
    
    const sourcesText = tpl.sources.map((s) => s.source_identifier).join(', ') || 'Не указаны';
    const statusClass = tpl.is_active ? 'ios-badge-active' : 'ios-badge-inactive';
    const statusText = tpl.is_active ? 'Активен' : 'Выключен';
    const lastRun = tpl.last_run_at ? new Date(tpl.last_run_at).toLocaleString('ru') : 'Никогда';
    
    card.innerHTML = `
      <div class="ios-template-header">
        <div class="ios-template-name">${escapeHtml(tpl.name)}</div>
        <div class="ios-template-meta">
          <span class="ios-list-item-badge ${statusClass}">${statusText}</span>
        </div>
      </div>
      <div class="ios-template-info">
        <div class="ios-template-info-row">
          <span class="ios-template-info-label">Источники</span>
          <span class="ios-template-info-value">${escapeHtml(sourcesText)}</span>
        </div>
        <div class="ios-template-info-row">
          <span class="ios-template-info-label">Куда</span>
          <span class="ios-template-info-value">${escapeHtml(tpl.target_chat_id)}</span>
        </div>
        <div class="ios-template-info-row">
          <span class="ios-template-info-label">Периодичность</span>
          <span class="ios-template-info-value">${tpl.frequency_hours} ч</span>
        </div>
        <div class="ios-template-info-row">
          <span class="ios-template-info-label">Последний запуск</span>
          <span class="ios-template-info-value">${lastRun}</span>
        </div>
      </div>
      <div class="ios-template-actions">
        <div class="ios-run-section">
          <select class="ios-form-input ios-form-select" data-role="run-period" data-id="${tpl.id}">
            <option value="6">6 ч</option>
            <option value="12">12 ч</option>
            <option value="24" selected>24 ч</option>
            <option value="48">48 ч</option>
          </select>
          <button class="ios-button ios-button-primary ios-button-small" data-action="run-now" data-id="${tpl.id}">
            Отправить
          </button>
        </div>
        <div class="ios-actions">
          <button class="ios-button ios-button-secondary ios-button-small" data-action="edit" data-id="${tpl.id}">
            Редактировать
          </button>
          <button class="ios-button ios-button-secondary ios-button-small" data-action="toggle" data-id="${tpl.id}">
            ${tpl.is_active ? 'Выключить' : 'Включить'}
          </button>
          <button class="ios-button ios-button-destructive ios-button-small" data-action="delete" data-id="${tpl.id}">
            Удалить
          </button>
        </div>
      </div>
    `;
    templatesContainer.appendChild(card);
  });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function openSheet(template = null) {
  form.reset();
  form.dataset.mode = template ? 'edit' : 'create';
  dialogTitle.textContent = template ? 'Редактирование' : 'Новый шаблон';
  document.getElementById('template-id').value = template?.id || '';
  document.getElementById('template-name').value = template?.name || '';
  document.getElementById('template-sources').value =
    template?.sources?.map((s) => s.source_identifier).join('\n') || '';
  document.getElementById('template-target').value = template?.target_chat_id || '';
  document.getElementById('template-frequency').value = template?.frequency_hours || '6';
  document.getElementById('template-active').checked = template?.is_active ?? true;
  targetsList.innerHTML = '';
  dialog.classList.add('open');
}

function closeSheet() {
  dialog.classList.remove('open');
}

async function submitTemplate(event) {
  event.preventDefault();
  const payload = {
    name: document.getElementById('template-name').value,
    sources: document
      .getElementById('template-sources')
      .value.split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
    target_chat_id: document.getElementById('template-target').value.trim(),
    frequency_hours: Number(document.getElementById('template-frequency').value),
    is_active: document.getElementById('template-active').checked,
  };

  const templateId = document.getElementById('template-id').value;
  const method = templateId ? 'PUT' : 'POST';
  const url = templateId ? `/api/templates/${templateId}` : '/api/templates/';

  saveBtn.disabled = true;
  saveBtn.textContent = '...';

  try {
    const response = await fetch(url, {
      method,
      headers: apiHeaders(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error('Не удалось сохранить');
    }

    closeSheet();
    loadTemplates();
  } catch (error) {
    tg?.showAlert?.(error.message) || alert(error.message);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Сохранить';
  }
}

async function loadTargets() {
  targetsList.innerHTML = '<div style="padding: 12px; color: var(--ios-text-secondary);">Загрузка...</div>';
  loadTargetsBtn.disabled = true;
  
  try {
    const res = await fetch('/api/templates/targets', { headers: apiHeaders() });
    if (!res.ok) throw new Error('Не удалось получить список чатов');
    const targets = await res.json();
    
    if (!targets.length) {
      targetsList.innerHTML = `
        <div style="padding: 16px; text-align: center; color: var(--ios-text-secondary); font-size: 14px;">
          Нет доступных чатов.<br>
          Напишите боту <code>/start -100XXX</code> чтобы зарегистрировать канал.
        </div>
      `;
      return;
    }
    
    targetsList.innerHTML = '';
    targets.forEach((t) => {
      const item = document.createElement('div');
      item.className = 'ios-target-item';
      
      const icon = t.chat_type === 'channel' ? '📢' : t.chat_type === 'supergroup' ? '👥' : '💬';
      const subtitle = t.username ? `@${t.username}` : t.id;
      
      item.innerHTML = `
        <div class="ios-target-icon">${icon}</div>
        <div class="ios-target-info">
          <div class="ios-target-title">${escapeHtml(t.title || 'Без названия')}</div>
          <div class="ios-target-subtitle">${escapeHtml(String(subtitle))}</div>
        </div>
      `;
      
      item.addEventListener('click', () => {
        document.getElementById('template-target').value = t.username ? '@' + t.username : t.id;
        // Visual feedback
        document.querySelectorAll('.ios-target-item').forEach(el => el.style.background = '');
        item.style.background = 'rgba(0, 122, 255, 0.1)';
      });
      
      targetsList.appendChild(item);
    });
  } catch (e) {
    targetsList.innerHTML = `<div style="padding: 12px; color: var(--ios-red);">Ошибка: ${e.message}</div>`;
  } finally {
    loadTargetsBtn.disabled = false;
  }
}

async function handleTemplateAction(event) {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;

  if (action === 'edit') {
    const response = await fetch('/api/templates/', { headers: apiHeaders() });
    const templates = await response.json();
    const template = templates.find((tpl) => String(tpl.id) === id);
    if (template) {
      openSheet(template);
    }
    return;
  }

  if (action === 'toggle') {
    button.disabled = true;
    await fetch(`/api/templates/${id}/toggle`, {
      method: 'POST',
      headers: apiHeaders(),
    });
    loadTemplates();
    return;
  }

  if (action === 'delete') {
    const confirmed = await new Promise((resolve) => {
      if (tg?.showConfirm) {
        tg.showConfirm('Удалить этот шаблон?', resolve);
      } else {
        resolve(confirm('Удалить шаблон?'));
      }
    });
    
    if (confirmed) {
      button.disabled = true;
      await fetch(`/api/templates/${id}`, {
        method: 'DELETE',
        headers: apiHeaders(),
      });
      loadTemplates();
    }
    return;
  }

  if (action === 'run-now') {
    button.disabled = true;
    const originalText = button.textContent;
    button.textContent = '...';
    button.classList.add('ios-loading');

    const select = document.querySelector(`select[data-role="run-period"][data-id="${id}"]`);
    const hours = select ? Number(select.value) : 24;

    try {
      const res = await fetch(`/api/templates/${id}/run-now?hours_back=${hours}`, {
        method: 'POST',
        headers: apiHeaders(),
      });

      if (res.ok) {
        await pollTemplateStatus(id, button, originalText);
      } else {
        tg?.showAlert?.('Ошибка при запуске') || alert('Ошибка при запуске');
        button.textContent = originalText;
        button.disabled = false;
        button.classList.remove('ios-loading');
      }
    } catch (e) {
      tg?.showAlert?.('Ошибка сети') || alert('Ошибка сети');
      button.textContent = originalText;
      button.disabled = false;
      button.classList.remove('ios-loading');
    }
  }
}

async function pollTemplateStatus(templateId, button, originalText) {
  const maxAttempts = 60;
  let attempts = 0;

  const poll = async () => {
    attempts++;
    try {
      const res = await fetch('/api/templates/', { headers: apiHeaders() });
      if (res.ok) {
        const templates = await res.json();
        const tpl = templates.find((t) => String(t.id) === String(templateId));
        if (tpl && !tpl.in_progress) {
          button.textContent = originalText;
          button.disabled = false;
          button.classList.remove('ios-loading');
          tg?.showAlert?.('Отправка завершена!') || alert('Отправка завершена!');
          loadTemplates();
          return;
        }
      }
    } catch (e) {
      // Ignore errors, keep polling
    }

    if (attempts < maxAttempts) {
      setTimeout(poll, 3000);
    } else {
      button.textContent = originalText;
      button.disabled = false;
      button.classList.remove('ios-loading');
      tg?.showAlert?.('Превышено время ожидания') || alert('Превышено время ожидания');
      loadTemplates();
    }
  };

  setTimeout(poll, 3000);
}

// Event Listeners
reloadBtn?.addEventListener('click', loadTemplates);
createBtn?.addEventListener('click', () => openSheet());
cancelBtn?.addEventListener('click', closeSheet);
sheetBackdrop?.addEventListener('click', closeSheet);
templatesContainer?.addEventListener('click', handleTemplateAction);
form?.addEventListener('submit', submitTemplate);
loadTargetsBtn?.addEventListener('click', loadTargets);

// Initial load
loadTemplates();

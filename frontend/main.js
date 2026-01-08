const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  // Set header color to match iOS style
  tg.setHeaderColor('#F2F2F7');
  tg.setBackgroundColor('#F2F2F7');
  // Debug: detailed logging
  console.log('[TG] === Telegram WebApp Debug ===');
  console.log('[TG] User ID:', tg.initDataUnsafe?.user?.id || 'NOT AVAILABLE');
  console.log('[TG] Username:', tg.initDataUnsafe?.user?.username || 'NOT AVAILABLE');
  console.log('[TG] initData present:', !!tg.initData);
  console.log('[TG] initData length:', tg.initData?.length || 0);
  console.log('[TG] initData first 100 chars:', tg.initData?.substring(0, 100) || 'EMPTY');
  console.log('[TG] initDataUnsafe:', JSON.stringify(tg.initDataUnsafe, null, 2));
  console.log('[TG] platform:', tg.platform);
  console.log('[TG] version:', tg.version);
} else {
  console.log('[TG] Telegram WebApp NOT AVAILABLE - running outside Telegram');
}

const apiHeaders = () => ({
  'Content-Type': 'application/json',
  'X-Telegram-Init-Data': tg?.initDataUnsafe ? tg.initData : '',
  'Cache-Control': 'no-cache, no-store, must-revalidate',
  'Pragma': 'no-cache',
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

// Loading overlay elements
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');
const loadingSubtext = document.getElementById('loading-subtext');

// Flag to prevent double-clicks
let isProcessing = false;

// Show/hide full-screen loading overlay (blocks ALL interactions)
function showLoadingOverlay(text = 'Отправка сводки...', subtext = 'Пожалуйста, подождите') {
  isProcessing = true;
  loadingText.textContent = text;
  loadingSubtext.textContent = subtext;
  loadingOverlay.classList.add('visible');
  document.body.classList.add('loading-active');
}

function hideLoadingOverlay() {
  isProcessing = false;
  loadingOverlay.classList.remove('visible');
  document.body.classList.remove('loading-active');
}

// Helper to show alert (handles both Telegram and browser)
function showMessage(message) {
  if (tg?.showAlert) {
    tg.showAlert(message);
  } else {
    alert(message);
  }
}

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
    const response = await fetch(`/api/templates/?_t=${Date.now()}`, {
      headers: apiHeaders(),
      cache: 'no-store',
    });
    if (!response.ok) {
      throw new Error(`Failed to load templates: ${response.status}`);
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
          <div class="ios-custom-dropdown" data-role="run-period" data-id="${tpl.id}" data-value="24">
            <div class="ios-dropdown-trigger">
              <span class="ios-dropdown-value">24 часа</span>
            </div>
            <div class="ios-dropdown-menu">
              <div class="ios-dropdown-option" data-value="6">6 часов</div>
              <div class="ios-dropdown-option" data-value="12">12 часов</div>
              <div class="ios-dropdown-option selected" data-value="24">24 часа</div>
              <div class="ios-dropdown-option" data-value="48">48 часов</div>
            </div>
          </div>
          <button class="ios-button ios-button-primary ios-button-small" data-action="run-now" data-id="${tpl.id}">
            Отправить
          </button>
        </div>
        <div class="ios-actions-grid">
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
  document.getElementById('template-custom-prompt').value = template?.custom_prompt || '';
  targetsList.innerHTML = '';
  dialog.classList.add('open');
}

function closeSheet() {
  dialog.classList.remove('open');
}

async function submitTemplate(event) {
  event.preventDefault();
  const customPrompt = document.getElementById('template-custom-prompt').value.trim();
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
    custom_prompt: customPrompt || null,
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
    showMessage(error.message);
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
      
      const icon = t.chat_type === 'channel' ? '📢' : t.chat_type === 'supergroup' ? '👥' : t.chat_type === 'private' ? '🤖' : '💬';
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
    // Prevent double-clicks
    if (isProcessing) {
      return;
    }

    const dropdown = document.querySelector(`.ios-custom-dropdown[data-role="run-period"][data-id="${id}"]`);
    const hours = dropdown ? Number(dropdown.dataset.value) : 24;

    // Show full-screen loading overlay (blocks entire screen)
    showLoadingOverlay('Отправка сводки...', `Собираем новости за ${hours} ч`);

    try {
      // Add timestamp to prevent caching
      const timestamp = Date.now();
      const res = await fetch(`/api/templates/${id}/run-now?hours_back=${hours}&_t=${timestamp}`, {
        method: 'POST',
        headers: apiHeaders(),
        cache: 'no-store',
      });

      hideLoadingOverlay();
      
      // Debug logging
      console.log(`[run-now] Status: ${res.status}, OK: ${res.ok}`);

      if (res.ok) {
        const result = await res.json();
        
        if (result.success) {
          let message = 'Сводка отправлена!';
          if (result.messages_count === 0) {
            message = 'Новых сообщений не найдено';
          } else if (result.total_tokens) {
            message = `Сводка отправлена! (${result.messages_count} сообщ., ${result.total_tokens} токенов)`;
          }
          showMessage(message);
        } else {
          const errorMsg = result.error || 'Неизвестная ошибка';
          showMessage(`Ошибка: ${errorMsg}`);
        }
      } else {
        const errorData = await res.json().catch(() => ({}));
        const errorMsg = errorData.detail || `Ошибка ${res.status}`;
        console.log(`[run-now] Error response:`, errorData);
        showMessage(errorMsg);
      }
      
      loadTemplates();
    } catch (e) {
      hideLoadingOverlay();
      console.error('[run-now] Network error:', e);
      showMessage(`Ошибка сети: ${e.message || 'проверьте подключение'}`);
    }
  }
}

// Event Listeners
reloadBtn?.addEventListener('click', loadTemplates);
createBtn?.addEventListener('click', () => openSheet());
cancelBtn?.addEventListener('click', closeSheet);
sheetBackdrop?.addEventListener('click', closeSheet);
templatesContainer?.addEventListener('click', handleTemplateAction);
form?.addEventListener('submit', submitTemplate);
loadTargetsBtn?.addEventListener('click', loadTargets);

// Custom Dropdown Logic
document.addEventListener('click', (e) => {
  // Handle dropdown trigger click
  const trigger = e.target.closest('.ios-dropdown-trigger');
  if (trigger) {
    const dropdown = trigger.closest('.ios-custom-dropdown');
    // Close all other dropdowns
    document.querySelectorAll('.ios-custom-dropdown.open').forEach(d => {
      if (d !== dropdown) d.classList.remove('open');
    });
    dropdown.classList.toggle('open');
    e.stopPropagation();
    return;
  }

  // Handle option click
  const option = e.target.closest('.ios-dropdown-option');
  if (option) {
    const dropdown = option.closest('.ios-custom-dropdown');
    const value = option.dataset.value;
    const text = option.textContent;
    
    // Update dropdown
    dropdown.dataset.value = value;
    dropdown.querySelector('.ios-dropdown-value').textContent = text;
    
    // Update selected state
    dropdown.querySelectorAll('.ios-dropdown-option').forEach(opt => {
      opt.classList.toggle('selected', opt === option);
    });
    
    dropdown.classList.remove('open');
    e.stopPropagation();
    return;
  }

  // Close dropdowns when clicking outside
  document.querySelectorAll('.ios-custom-dropdown.open').forEach(d => {
    d.classList.remove('open');
  });
});

// Block all clicks on loading overlay
loadingOverlay?.addEventListener('click', (e) => {
  e.preventDefault();
  e.stopPropagation();
});

// Also block touch events on overlay
loadingOverlay?.addEventListener('touchstart', (e) => {
  e.preventDefault();
  e.stopPropagation();
}, { passive: false });

// Initial load
loadTemplates();

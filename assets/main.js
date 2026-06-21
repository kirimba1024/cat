// Имя и контакты берём из data-* у <main class="page"> — меняешь в одном месте.
(function () {
  const p = document.querySelector('.page');
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  set('name', p.dataset.name);
  set('breed', p.dataset.breed);
  document.title = p.dataset.name + ' · ' + p.dataset.breed;

  const tg = p.dataset.telegram;
  const tgBtn = document.getElementById('tgBtn');
  if (tgBtn) tgBtn.href = 'https://t.me/' + tg;
  set('tgText', 't.me/' + tg);

  const mail = p.dataset.email;
  const mailBtn = document.getElementById('mailBtn');
  if (mailBtn) mailBtn.href = 'mailto:' + mail;
  set('mailText', mail);

  const upd = document.getElementById('updated');
  if (upd) {
    upd.textContent = new Date(document.lastModified).toLocaleDateString('ru-RU', {
      day: 'numeric', month: 'long', year: 'numeric'
    });
  }
})();

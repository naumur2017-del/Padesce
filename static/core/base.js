// Navigation menu toggle
(function() {
  const nav = document.getElementById('appNav');
  const menu = document.getElementById('navMenu');
  const toggle = document.getElementById('navToggle');
  const dropdown = document.getElementById('navDropdown');

  if (nav) {
    const syncScrolledState = () => {
      nav.classList.toggle('is-scrolled', window.scrollY > 10);
    };
    window.addEventListener('scroll', syncScrolledState, { passive: true });
    syncScrolledState();
  }

  if (!menu || !toggle || !dropdown) {
    return;
  }

  const setExpanded = (expanded) => {
    menu.classList.toggle('open', expanded);
    toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  };

  toggle.addEventListener('click', (event) => {
    event.preventDefault();
    setExpanded(!menu.classList.contains('open'));
  });

  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target)) {
      setExpanded(false);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setExpanded(false);
    }
  });

  dropdown.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => setExpanded(false));
  });
})();

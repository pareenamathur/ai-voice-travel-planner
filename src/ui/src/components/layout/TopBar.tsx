/** Top bar search + utility icons. */

export interface TopBarProps {
  placeholder?: string;
}

export function TopBar({ placeholder = "Search destinations..." }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar__search">
        <input
          type="search"
          className="top-bar__input"
          placeholder={placeholder}
          aria-label={placeholder}
        />
        <span className="material-symbols-outlined top-bar__search-icon" aria-hidden="true">
          search
        </span>
      </div>
      <div className="top-bar__actions">
        <button type="button" className="top-bar__icon-btn" aria-label="Notifications">
          <span className="material-symbols-outlined" aria-hidden="true">
            notifications
          </span>
        </button>
        <button type="button" className="top-bar__icon-btn" aria-label="Account">
          <span className="material-symbols-outlined" aria-hidden="true">
            account_circle
          </span>
        </button>
      </div>
    </header>
  );
}

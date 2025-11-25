'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';

interface WeekOption {
  label: string;
  anchor: string;
}

interface WeekDropdownProps {
  weeks: WeekOption[];
  selectedWeek: string | null;
  currentWeek: string | null;
}

function scrollToWeek(anchor: string | null) {
  if (!anchor || anchor === 'all') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }

  const section = document.getElementById(`week-${anchor}`);
  if (section) {
    section.classList.add('week-section-highlight');
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.setTimeout(() => {
      section.classList.remove('week-section-highlight');
    }, 1800);
  }
}

export default function WeekDropdown({
  weeks,
  selectedWeek,
  currentWeek,
}: WeekDropdownProps) {
  const defaultValue = useMemo(() => {
    const match = weeks.find(option => option.label === selectedWeek);
    return match?.anchor ?? 'all';
  }, [weeks, selectedWeek]);

  const currentValue = useMemo(() => {
    const match = weeks.find(option => option.label === currentWeek);
    return match?.anchor ?? null;
  }, [weeks, currentWeek]);

  const [value, setValue] = useState(defaultValue);

  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const newValue = event.target.value;
    setValue(newValue);
    scrollToWeek(newValue === 'all' ? null : newValue);
  };

  const handleReset = () => {
    if (currentValue) {
      setValue(currentValue);
      scrollToWeek(currentValue);
    }
  };

  return (
    <div className="week-dropdown">
      <label htmlFor="week-select" className="week-dropdown-label">
        Delivery week
      </label>
      <div className="week-dropdown-controls">
        <select
          id="week-select"
          className="week-select"
          value={value}
          onChange={handleChange}
          disabled={weeks.length === 0}
        >
          <option value="all">All available weeks</option>
          {weeks.map(week => (
            <option key={week.anchor} value={week.anchor}>
              {week.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="week-reset-button"
          onClick={handleReset}
          disabled={
            !currentValue || currentValue === value || weeks.length === 0
          }
        >
          Jump to current week
        </button>
      </div>
      <p className="week-dropdown-hint">
        Use the dropdown to jump straight to any delivery week.
      </p>
    </div>
  );
}

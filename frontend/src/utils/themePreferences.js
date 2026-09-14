export function normalizeTheme(theme) {
  return theme === "light" ? "light" : "dark";
}

export async function saveThemePreference(theme, savePreference) {
  try {
    await savePreference(theme);
    return true;
  } catch (error) {
    console.error("Could not save theme preference:", error);
    return false;
  }
}

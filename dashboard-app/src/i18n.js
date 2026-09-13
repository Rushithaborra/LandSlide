// react-i18next setup. Only the highest-traffic surfaces (Sidebar, Topbar,
// Overview) are translated so far -- see README.md for what's still
// English-only. Hindi and Nepali chosen for Sikkim's actual linguistic
// makeup (Nepali is the state's majority language); translations here are
// machine-quality, not reviewed by a native speaker -- flag this if asked.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import hi from "./locales/hi.json";
import ne from "./locales/ne.json";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    ne: { translation: ne },
  },
  lng: localStorage.getItem("language") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React already escapes
});

export default i18n;

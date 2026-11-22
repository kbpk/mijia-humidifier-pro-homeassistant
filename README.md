# Mijia Smart Evaporative Humidifier Pro

Lokalna integracja Home Assistant dla `xiaomi.humidifier.600ek`. Wysyła polecenia MIoT przez szyfrowany protokół MiIO do portu UDP 54321 nawilżacza. Integracja korzysta z adresu IPv4 i tokenu urządzenia. Podczas pracy łączy się bezpośrednio z nawilżaczem.

## Funkcje

- Zasilanie, wilgotność docelowa 40–70% i tryby stałej wilgotności, nocny, intensywny oraz suszenie filtra.
- Pomiar wilgotności, pozostały czas suszenia, kod błędu i czujnik braku wody.
- Wyświetlacz i jego jasność, sygnały dźwiękowe, blokada rodzicielska i ochrona przed nadmierną wilgotnością.

Brak wody jest odczytywany z kodu błędu MIoT 4. Dostępność dodatkowych encji zależy od właściwości zwracanych przez firmware. Ustawienie trybu suszenia bezpośrednim zapisem MIoT wymaga potwierdzenia na urządzeniu.

## Instalacja

Integracja jest przygotowana dla linii Home Assistant 2026.11.

- **Marketplace:** otwórz **Ustawienia → Marketplace → Dodaj z linku** i podaj adres publicznego repozytorium GitHub z tym kodem. Marketplace może poprosić o połączenie z GitHubem. Otwórz pozycję integracji i wybierz instalację.
- **Ręcznie:** skopiuj katalog `custom_components/mijia_humidifier_pro` do `custom_components` w katalogu konfiguracji Home Assistant i uruchom HA ponownie.

## Konfiguracja

W **Ustawienia → Urządzenia i usługi → Dodaj integrację** wybierz **Mijia Smart Evaporative Humidifier Pro**. Wpisz adres IPv4 i token MiIO nawilżacza (32 znaki szesnastkowe). Token urządzenia wklej tylko do formularza HA. Zmianę adresu lub tokenu wykonasz przez **Konfiguruj ponownie**.

Formularz wykonuje uwierzytelniony odczyt modelu i stanu. Jeśli nie otrzymuje odpowiedzi na handshake, sprawdź adres i dostęp z hosta HA do portu UDP 54321. Jeśli odpowiada tylko handshake, sprawdź aktualny token i obsługę poleceń lokalnych przez firmware. Przy odświeżaniu połączenie próbuje ponownie po przejściowym błędzie komunikacji. Polecenia zmiany stanu są wysyłane jeden raz.

## Źródła

- [Właściwości MIoT modelu 600ek](https://home.miot-spec.com/en/spec/xiaomi.humidifier.600ek)
- [Kod transportu MiIO w integracji Philips SREAD1](https://github.com/kbpk/philips-sread1-homeassistant)

Licencja MIT.

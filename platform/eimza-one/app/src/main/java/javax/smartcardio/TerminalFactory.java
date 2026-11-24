package javax.smartcardio;

import java.security.Provider;
import java.security.Security;

public final class TerminalFactory {
    private final String type;
    private final Provider provider;
    private final CardTerminals terminals;

    private TerminalFactory(String type, Provider provider, Object parameters) throws CardException {
        this.type = type; this.provider = provider;
        Provider.Service service = provider.getService("TerminalFactory", type);
        if (service == null) throw new CardException("Provider does not support " + type);
        try {
            TerminalFactorySpi spi;
            if ("AndroidCCID".equals(provider.getName()) || provider instanceof app.eimza.mobile.AndroidCcidProvider) {
                spi = new app.eimza.mobile.AndroidCcidProvider.Factory(parameters);
            } else {
                spi = (TerminalFactorySpi) service.newInstance(parameters);
            }
            this.terminals = spi.engineTerminals();
        }
        catch (Exception e) { throw new CardException("Cannot create terminal factory", e); }
    }

    public static TerminalFactory getDefault() {
        String type = Security.getProperty("javax.smartcardio.TerminalFactory.DefaultType");
        if (type == null || type.length() == 0) type = System.getProperty("javax.smartcardio.TerminalFactory.DefaultType", "PC/SC");
        for (Provider p : Security.getProviders()) {
            if (p.getService("TerminalFactory", type) != null) {
                try { return new TerminalFactory(type, p, null); } catch (CardException ignored) { }
            }
        }
        throw new IllegalStateException("No javax.smartcardio provider for " + type);
    }

    public static TerminalFactory getInstance(String type, Object parameters) throws CardException {
        for (Provider p : Security.getProviders()) if (p.getService("TerminalFactory", type) != null) return new TerminalFactory(type, p, parameters);
        throw new CardException("No provider for terminal factory type " + type);
    }
    public static TerminalFactory getInstance(String type, Object parameters, String provider) throws CardException {
        Provider p = Security.getProvider(provider); if (p == null) throw new CardException("Provider not found: " + provider);
        return new TerminalFactory(type, p, parameters);
    }
    public static TerminalFactory getInstance(String type, Object parameters, Provider provider) throws CardException {
        if (provider == null) throw new NullPointerException("provider");
        return new TerminalFactory(type, provider, parameters);
    }
    public String getType() { return type; }
    public Provider getProvider() { return provider; }
    public CardTerminals terminals() { return terminals; }
}

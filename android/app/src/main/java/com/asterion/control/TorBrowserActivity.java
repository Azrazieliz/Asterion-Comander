package com.asterion.control;

/** Same Browser UI and WebView engine, isolated proxy and storage process. */
public final class TorBrowserActivity extends BrowserActivity {
    @Override protected boolean torMode(){return true;}
}

package com.asterion.control;

import android.app.ActivityManager;
import android.content.Context;
import android.os.Build;
import android.os.PowerManager;
import org.json.JSONObject;

/** Samples Android-managed resources immediately before allocating a model context. */
final class OnDeviceModelResources {
    final ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
    final int thermalStatus;
    final int availableProcessors;

    OnDeviceModelResources(Context context) {
        context.getSystemService(ActivityManager.class).getMemoryInfo(memory);
        PowerManager power = context.getSystemService(PowerManager.class);
        thermalStatus = power == null ? -1 : power.getCurrentThermalStatus();
        availableProcessors = Runtime.getRuntime().availableProcessors();
    }

    JSONObject status(Context context) throws Exception {
        return new JSONObject()
            .put("device_model", Build.MODEL)
            .put("soc_manufacturer", Build.VERSION.SDK_INT >= 31 ? Build.SOC_MANUFACTURER : JSONObject.NULL)
            .put("soc_model", Build.VERSION.SDK_INT >= 31 ? Build.SOC_MODEL : JSONObject.NULL)
            .put("available_processors", availableProcessors)
            .put("android_vulkan_feature", context.getPackageManager().hasSystemFeature("android.hardware.vulkan.version"))
            .put("thermal_status", thermalStatus)
            .put("android_low_memory", memory.lowMemory)
            .put("available_bytes", memory.availMem)
            .put("total_bytes", memory.totalMem);
    }

    int threads() {
        return Math.max(1, Math.min(thermalStatus >= PowerManager.THERMAL_STATUS_MODERATE ? 2 : 4,
            availableProcessors));
    }

    int contextTokens(OnDeviceModelProfile profile,int outputTokens,boolean alreadyLoaded) {
        if (memory.lowMemory) throw new IllegalStateException("android_memory_pressure");
        if (thermalStatus >= PowerManager.THERMAL_STATUS_SEVERE)
            throw new IllegalStateException("android_thermal_pressure");
        long reserve = Math.max(memory.threshold, 384L << 20);
        long weights = alreadyLoaded ? 0 : profile.residentBytes + profile.adapterBytes;
        long remaining = memory.availMem - reserve - weights - profile.workspaceBytes;
        if (remaining < 0) throw new IllegalStateException("model_runtime_memory_budget_exceeded");
        int context = profile.contextTokens;
        if (profile.kvBytesPerToken > 0 && remaining / profile.kvBytesPerToken < context) {
            if (!profile.allowSmallerContext)
                throw new IllegalStateException("model_context_memory_budget_exceeded");
            context = (int)(remaining / profile.kvBytesPerToken / 256 * 256);
        }
        if (context < Math.max(512, outputTokens + 256))
            throw new IllegalStateException("model_context_memory_budget_exceeded");
        return context;
    }
}

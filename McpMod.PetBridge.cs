using System;
using System.Collections.Generic;
using System.Linq;

namespace STS2_MCP;

public sealed record PetModeRequest(string? Mode);

public sealed record PetMessageRequest(
    string? Mode,
    string? State,
    string? Title,
    IReadOnlyList<string>? Lines);

public sealed record PetStatusResponse(
    string Status,
    string Mode,
    string State,
    string Title,
    IReadOnlyList<string> Lines);

public sealed record PetBridgeResult<T>(
    int StatusCode,
    T? Payload,
    string? Error)
{
    public bool IsSuccess => StatusCode is >= 200 and < 300 && Error == null;

    public static PetBridgeResult<T> Success(T payload) => new(200, payload, null);

    public static PetBridgeResult<T> Failure(int statusCode, string error) => new(statusCode, default, error);
}

public sealed class PetBridgeService
{
    private readonly PetStateStore _store;

    public PetBridgeService(PetStateStore store)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    public PetBridgeResult<PetStatusResponse> GetStatus()
    {
        return PetBridgeResult<PetStatusResponse>.Success(ToResponse(_store.Snapshot()));
    }

    public PetBridgeResult<PetStatusResponse> SetMode(PetModeRequest? request)
    {
        if (!TryParseMode(request?.Mode, out var mode, out var error))
            return PetBridgeResult<PetStatusResponse>.Failure(400, error);

        _store.SetMode(mode);
        return GetStatus();
    }

    public PetBridgeResult<PetStatusResponse> SetMessage(PetMessageRequest? request)
    {
        if (!TryParseMode(request?.Mode, out var mode, out var modeError))
            return PetBridgeResult<PetStatusResponse>.Failure(400, modeError);

        if (!TryParseState(request?.State, out var state, out var stateError))
            return PetBridgeResult<PetStatusResponse>.Failure(400, stateError);

        _store.SetMessage(new PetMessagePayload(
            mode,
            state,
            request?.Title ?? string.Empty,
            NormalizeLines(request?.Lines)));

        return GetStatus();
    }

    private static PetStatusResponse ToResponse(PetStateSnapshot snapshot)
    {
        return new PetStatusResponse(
            "ok",
            ToApiValue(snapshot.Mode),
            ToApiValue(snapshot.State),
            snapshot.Title,
            snapshot.Lines.Count == 0 ? Array.Empty<string>() : snapshot.Lines.ToArray());
    }

    private static IReadOnlyList<string> NormalizeLines(IReadOnlyList<string>? lines)
    {
        if (lines == null || lines.Count == 0)
            return Array.Empty<string>();

        return lines.Select(line => line ?? string.Empty).ToArray();
    }

    private static bool TryParseMode(string? rawMode, out PetMode mode, out string error)
    {
        var normalized = Normalize(rawMode);
        switch (normalized)
        {
            case "pause":
                mode = PetMode.Pause;
                error = string.Empty;
                return true;
            case "advise":
                mode = PetMode.Advise;
                error = string.Empty;
                return true;
            case "auto":
                mode = PetMode.Auto;
                error = string.Empty;
                return true;
            default:
                mode = default;
                error = $"Invalid mode '{normalized}'. Expected pause, advise, or auto.";
                return false;
        }
    }

    private static bool TryParseState(string? rawState, out PetVisualState state, out string error)
    {
        var normalized = Normalize(rawState);
        switch (normalized)
        {
            case "idle":
                state = PetVisualState.Idle;
                error = string.Empty;
                return true;
            case "thinking":
                state = PetVisualState.Thinking;
                error = string.Empty;
                return true;
            case "talking":
                state = PetVisualState.Talking;
                error = string.Empty;
                return true;
            case "auto_running":
                state = PetVisualState.AutoRunning;
                error = string.Empty;
                return true;
            case "paused":
                state = PetVisualState.Paused;
                error = string.Empty;
                return true;
            case "error":
                state = PetVisualState.Error;
                error = string.Empty;
                return true;
            default:
                state = default;
                error =
                    $"Invalid state '{normalized}'. Expected idle, thinking, talking, auto_running, paused, or error.";
                return false;
        }
    }

    private static string Normalize(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim().ToLowerInvariant();
    }

    private static string ToApiValue(PetMode mode)
    {
        return mode switch
        {
            PetMode.Pause => "pause",
            PetMode.Advise => "advise",
            PetMode.Auto => "auto",
            _ => "pause"
        };
    }

    private static string ToApiValue(PetVisualState state)
    {
        return state switch
        {
            PetVisualState.Idle => "idle",
            PetVisualState.Thinking => "thinking",
            PetVisualState.Talking => "talking",
            PetVisualState.AutoRunning => "auto_running",
            PetVisualState.Paused => "paused",
            PetVisualState.Error => "error",
            _ => "paused"
        };
    }
}

using System;
using System.Collections.Generic;
using System.Linq;

namespace STS2_MCP;

public enum PetMode
{
    Pause,
    Advise,
    Auto
}

public enum PetVisualState
{
    Idle,
    Thinking,
    Talking,
    AutoRunning,
    Paused,
    Error
}

public sealed record PetMessagePayload(
    PetMode Mode,
    PetVisualState State,
    string Title,
    IReadOnlyList<string> Lines);

public sealed record PetStateSnapshot(
    PetMode Mode,
    PetVisualState State,
    string Title,
    IReadOnlyList<string> Lines,
    bool MenuOpen);

public sealed class PetStateStore
{
    private readonly object _gate = new();
    private PetStateSnapshot _snapshot = CreateDefaultSnapshot();

    public PetStateSnapshot Snapshot()
    {
        lock (_gate)
        {
            return _snapshot with { Lines = CopyLines(_snapshot.Lines) };
        }
    }

    public void SetMode(PetMode mode)
    {
        lock (_gate)
        {
            _snapshot = _snapshot with
            {
                Mode = mode,
                State = mode == PetMode.Pause ? PetVisualState.Paused : PetVisualState.Idle,
                Title = string.Empty,
                Lines = Array.Empty<string>()
            };
        }
    }

    public void ToggleMenu()
    {
        lock (_gate)
        {
            _snapshot = _snapshot with { MenuOpen = !_snapshot.MenuOpen };
        }
    }

    public void SetMenuOpen(bool isOpen)
    {
        lock (_gate)
        {
            if (_snapshot.MenuOpen == isOpen)
                return;

            _snapshot = _snapshot with { MenuOpen = isOpen };
        }
    }

    public void SetMessage(PetMessagePayload payload)
    {
        ArgumentNullException.ThrowIfNull(payload);

        lock (_gate)
        {
            _snapshot = new PetStateSnapshot(
                payload.Mode,
                payload.State,
                payload.Title ?? string.Empty,
                CopyLines(payload.Lines),
                _snapshot.MenuOpen);
        }
    }

    private static PetStateSnapshot CreateDefaultSnapshot()
    {
        return new PetStateSnapshot(
            PetMode.Pause,
            PetVisualState.Paused,
            string.Empty,
            Array.Empty<string>(),
            false);
    }

    private static IReadOnlyList<string> CopyLines(IReadOnlyList<string> lines)
    {
        return lines.Count == 0 ? Array.Empty<string>() : lines.ToArray();
    }
}

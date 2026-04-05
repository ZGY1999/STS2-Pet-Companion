using System.Collections.Generic;
using Xunit;
using STS2_MCP;

namespace STS2_MCP.Tests;

public class PetStateStoreTests
{
    [Fact]
    public void DefaultSnapshot_UsesPausedPetState()
    {
        var store = new PetStateStore();

        var snapshot = store.Snapshot();

        Assert.Equal(PetMode.Pause, snapshot.Mode);
        Assert.Equal(PetVisualState.Paused, snapshot.State);
        Assert.Equal(string.Empty, snapshot.Title);
        Assert.Empty(snapshot.Lines);
        Assert.False(snapshot.MenuOpen);
    }

    [Fact]
    public void SetMode_TransitionsVisualState_AndClearsBubble()
    {
        var store = new PetStateStore();
        store.SetMessage(new PetMessagePayload(
            PetMode.Auto,
            PetVisualState.Talking,
            "Companion",
            new List<string> { "Line 1" }));

        store.SetMode(PetMode.Advise);

        var advise = store.Snapshot();
        Assert.Equal(PetMode.Advise, advise.Mode);
        Assert.Equal(PetVisualState.Idle, advise.State);
        Assert.Equal(string.Empty, advise.Title);
        Assert.Empty(advise.Lines);

        store.SetMode(PetMode.Auto);

        var auto = store.Snapshot();
        Assert.Equal(PetMode.Auto, auto.Mode);
        Assert.Equal(PetVisualState.Idle, auto.State);
        Assert.Equal(string.Empty, auto.Title);
        Assert.Empty(auto.Lines);

        store.SetMode(PetMode.Pause);

        var pause = store.Snapshot();
        Assert.Equal(PetMode.Pause, pause.Mode);
        Assert.Equal(PetVisualState.Paused, pause.State);
        Assert.Equal(string.Empty, pause.Title);
        Assert.Empty(pause.Lines);
    }

    [Fact]
    public void SetMessage_StoresPayloadContents()
    {
        var store = new PetStateStore();
        var payload = new PetMessagePayload(
            PetMode.Auto,
            PetVisualState.Talking,
            "Companion",
            new List<string> { "Hello", "World" });

        store.SetMessage(payload);

        var snapshot = store.Snapshot();

        Assert.Equal(PetMode.Auto, snapshot.Mode);
        Assert.Equal(PetVisualState.Talking, snapshot.State);
        Assert.Equal("Companion", snapshot.Title);
        Assert.Equal(new[] { "Hello", "World" }, snapshot.Lines);
        Assert.False(snapshot.MenuOpen);
    }

    [Fact]
    public void Snapshot_Returns_DefensiveCopyOfLines()
    {
        var store = new PetStateStore();
        store.SetMessage(new PetMessagePayload(
            PetMode.Auto,
            PetVisualState.Talking,
            "Companion",
            new List<string> { "Hello" }));

        var snapshot = store.Snapshot();
        var lines = Assert.IsType<string[]>(snapshot.Lines);
        lines[0] = "Mutated";

        Assert.Equal("Hello", store.Snapshot().Lines[0]);
    }

    [Fact]
    public void SetMenuOpen_ControlsMenuStateExplicitly()
    {
        var store = new PetStateStore();

        store.SetMenuOpen(true);
        Assert.True(store.Snapshot().MenuOpen);

        store.SetMenuOpen(true);
        Assert.True(store.Snapshot().MenuOpen);

        store.SetMenuOpen(false);
        Assert.False(store.Snapshot().MenuOpen);
    }
}

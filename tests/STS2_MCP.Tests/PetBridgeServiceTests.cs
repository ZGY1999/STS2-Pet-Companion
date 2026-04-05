using System.Collections.Generic;
using STS2_MCP;
using Xunit;

namespace STS2_MCP.Tests;

public class PetBridgeServiceTests
{
    [Fact]
    public void GetStatus_Returns_DefaultSnapshot_AsApiPayload()
    {
        var service = new PetBridgeService(new PetStateStore());

        var result = service.GetStatus();

        Assert.True(result.IsSuccess);
        Assert.Equal(200, result.StatusCode);
        Assert.Null(result.Error);
        Assert.NotNull(result.Payload);
        Assert.Equal("ok", result.Payload!.Status);
        Assert.Equal("pause", result.Payload.Mode);
        Assert.Equal("paused", result.Payload.State);
        Assert.Equal(string.Empty, result.Payload.Title);
        Assert.Empty(result.Payload.Lines);
    }

    [Fact]
    public void SetMode_Updates_StoredMode_AndReturnsLatestStatus()
    {
        var service = new PetBridgeService(new PetStateStore());
        service.SetMessage(new PetMessageRequest(
            "advise",
            "talking",
            "Companion",
            new List<string> { "Line 1" }));

        var result = service.SetMode(new PetModeRequest("auto"));

        Assert.True(result.IsSuccess);
        Assert.Equal(200, result.StatusCode);
        Assert.NotNull(result.Payload);
        Assert.Equal("auto", result.Payload!.Mode);
        Assert.Equal("idle", result.Payload.State);
        Assert.Equal(string.Empty, result.Payload.Title);
        Assert.Empty(result.Payload.Lines);
        Assert.Equal("auto", service.GetStatus().Payload!.Mode);
    }

    [Fact]
    public void SetMode_Rejects_UnknownMode()
    {
        var service = new PetBridgeService(new PetStateStore());

        var result = service.SetMode(new PetModeRequest("turbo"));

        Assert.False(result.IsSuccess);
        Assert.Equal(400, result.StatusCode);
        Assert.Equal("Invalid mode 'turbo'. Expected pause, advise, or auto.", result.Error);
        Assert.Null(result.Payload);
    }

    [Fact]
    public void SetMessage_StoresMessagePayload_AndNormalizesResponse()
    {
        var service = new PetBridgeService(new PetStateStore());

        var result = service.SetMessage(new PetMessageRequest(
            "advise",
            "talking",
            "Companion",
            new List<string> { "Line 1", "Line 2" }));

        Assert.True(result.IsSuccess);
        Assert.Equal(200, result.StatusCode);
        Assert.NotNull(result.Payload);
        Assert.Equal("ok", result.Payload!.Status);
        Assert.Equal("advise", result.Payload.Mode);
        Assert.Equal("talking", result.Payload.State);
        Assert.Equal("Companion", result.Payload.Title);
        Assert.Equal(new[] { "Line 1", "Line 2" }, result.Payload.Lines);
    }

    [Fact]
    public void SetMessage_Rejects_UnknownState()
    {
        var service = new PetBridgeService(new PetStateStore());

        var result = service.SetMessage(new PetMessageRequest(
            "advise",
            "celebrating",
            "Companion",
            new List<string> { "Line 1" }));

        Assert.False(result.IsSuccess);
        Assert.Equal(400, result.StatusCode);
        Assert.Equal(
            "Invalid state 'celebrating'. Expected idle, thinking, talking, auto_running, paused, or error.",
            result.Error);
        Assert.Null(result.Payload);
    }
}

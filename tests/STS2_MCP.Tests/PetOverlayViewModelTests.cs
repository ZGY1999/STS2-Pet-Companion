using System.Collections.Generic;
using System.Reflection;
using STS2_MCP;
using Xunit;

namespace STS2_MCP.Tests;

public class PetOverlayViewModelTests
{
    [Fact]
    public void ToggleMenu_Flips_MenuState_WithoutChangingPetMessage()
    {
        var store = new PetStateStore();
        store.SetMessage(new PetMessagePayload(
            PetMode.Advise,
            PetVisualState.Talking,
            "Companion",
            new List<string> { "Line 1", "Line 2" }));

        store.ToggleMenu();
        var opened = store.Snapshot();

        Assert.True(opened.MenuOpen);
        Assert.Equal(PetMode.Advise, opened.Mode);
        Assert.Equal(PetVisualState.Talking, opened.State);
        Assert.Equal("Companion", opened.Title);
        Assert.Equal(new[] { "Line 1", "Line 2" }, opened.Lines);

        store.ToggleMenu();

        Assert.False(store.Snapshot().MenuOpen);
    }

    [Fact]
    public void FromSnapshot_Builds_BadgeBubbleAndMenuState()
    {
        var viewModel = PetOverlayViewModel.FromSnapshot(new PetStateSnapshot(
            PetMode.Auto,
            PetVisualState.Thinking,
            "Pet",
            new[] { "Plan first", "Then act" },
            true));

        Assert.Equal("AUTO", viewModel.ModeBadgeText);
        Assert.Equal("Pet", viewModel.BubbleTitle);
        Assert.Equal("Plan first\nThen act", viewModel.BubbleText);
        Assert.True(viewModel.ShowBubble);
        Assert.True(viewModel.ShowMenu);
        Assert.Equal(3, viewModel.MenuItems.Count);
        Assert.Equal("Pause", viewModel.MenuItems[0].Label);
        Assert.False(viewModel.MenuItems[0].IsSelected);
        Assert.True(viewModel.MenuItems[2].IsSelected);
    }

    [Fact]
    public void HasEquivalentMenu_IgnoresBubbleAndVisualStateChanges()
    {
        var first = PetOverlayViewModel.FromSnapshot(new PetStateSnapshot(
            PetMode.Advise,
            PetVisualState.Thinking,
            "Thinking",
            new[] { "Line 1" },
            true));
        var second = PetOverlayViewModel.FromSnapshot(new PetStateSnapshot(
            PetMode.Advise,
            PetVisualState.Talking,
            "Answer",
            new[] { "Line 2", "Line 3" },
            true));
        var differentMode = PetOverlayViewModel.FromSnapshot(new PetStateSnapshot(
            PetMode.Auto,
            PetVisualState.Talking,
            "Answer",
            new[] { "Line 2" },
            true));

        Assert.True(first.HasEquivalentMenu(second));
        Assert.False(first.HasEquivalentMenu(differentMode));
    }

    [Theory]
    [InlineData(PetVisualState.Idle, "Wide", "Rest", false, false, false, false)]
    [InlineData(PetVisualState.Thinking, "Focused", "Gesture", false, false, false, false)]
    [InlineData(PetVisualState.Talking, "Wide", "Talk", true, true, false, false)]
    [InlineData(PetVisualState.AutoRunning, "Focused", "Dash", false, false, true, false)]
    [InlineData(PetVisualState.Paused, "Closed", "Rest", false, false, false, false)]
    [InlineData(PetVisualState.Error, "Crossed", "Rest", false, false, false, true)]
    public void OwlVisualSpec_FromState_UsesReadablePoseAndExpressionMapping(
        PetVisualState state,
        string expectedEyeState,
        string expectedWingPose,
        bool expectedBeakOpen,
        bool expectedTalkWaves,
        bool expectedSpeedLines,
        bool expectedRuffled)
    {
        var spec = CreateOwlSpec(state);

        Assert.Equal(expectedEyeState, ReadEnumName(spec, "EyeState"));
        Assert.Equal(expectedWingPose, ReadEnumName(spec, "WingPose"));
        Assert.Equal(expectedBeakOpen, ReadBoolean(spec, "BeakOpen"));
        Assert.Equal(expectedTalkWaves, ReadBoolean(spec, "ShowTalkWaves"));
        Assert.Equal(expectedSpeedLines, ReadBoolean(spec, "ShowSpeedLines"));
        Assert.Equal(expectedRuffled, ReadBoolean(spec, "IsRuffled"));
        Assert.True(ReadBoolean(spec, "ShowChestRune"));
    }

    [Fact]
    public void OwlVisualSpec_FromState_GivesThinkingAndAutoDistinctSilhouettes()
    {
        var thinking = CreateOwlSpec(PetVisualState.Thinking);
        var autoRunning = CreateOwlSpec(PetVisualState.AutoRunning);

        Assert.NotEqual(ReadEnumName(thinking, "WingPose"), ReadEnumName(autoRunning, "WingPose"));
        Assert.True(ReadSingle(thinking, "HeadTilt") < 0f);
        Assert.True(ReadSingle(autoRunning, "BodyLean") > 0f);
    }

    [Fact]
    public void OwlRenderRecipe_Defaults_ToLargeHeadReadableFaceAndSupersampledTexture()
    {
        var recipe = CreateRenderRecipe(PetVisualState.Idle);

        Assert.Equal(136, ReadInt32(recipe, "TextureSize"));
        Assert.True(ReadSingle(recipe, "HeadRadiusY") > ReadSingle(recipe, "BodyRadiusX"));
        Assert.True(ReadSingle(recipe, "FaceRadiusX") > ReadSingle(recipe, "EyeRadius") * 2.5f);
        Assert.True(ReadSingle(recipe, "OutlineThickness") >= 2f);
    }

    [Fact]
    public void OwlRenderRecipe_StateVariants_EmphasizeMotionSpeechAndErrorReadability()
    {
        var idle = CreateRenderRecipe(PetVisualState.Idle);
        var talking = CreateRenderRecipe(PetVisualState.Talking);
        var autoRunning = CreateRenderRecipe(PetVisualState.AutoRunning);
        var error = CreateRenderRecipe(PetVisualState.Error);

        Assert.True(ReadSingle(talking, "WingLift") < ReadSingle(idle, "WingLift"));
        Assert.True(ReadSingle(talking, "RuneScale") >= ReadSingle(idle, "RuneScale"));
        Assert.True(ReadSingle(autoRunning, "MotionLineLength") > 0f);
        Assert.True(ReadSingle(autoRunning, "WingForward") > ReadSingle(idle, "WingForward"));
        Assert.True(ReadSingle(error, "FeatherJitter") > 0f);
    }

    [Theory]
    [InlineData(PetVisualState.Idle, "pet/owl/idle.png")]
    [InlineData(PetVisualState.Thinking, "pet/owl/thinking.png")]
    [InlineData(PetVisualState.Talking, "pet/owl/talking.png")]
    [InlineData(PetVisualState.AutoRunning, "pet/owl/auto_running.png")]
    [InlineData(PetVisualState.Paused, "pet/owl/paused.png")]
    [InlineData(PetVisualState.Error, "pet/owl/error.png")]
    public void OwlAssetManifest_MapsStatesToStableRelativePngPaths(PetVisualState state, string expectedPath)
    {
        var manifest = CreateAssetManifest();
        var relativePath = InvokeStringMethod(manifest, "GetRelativePath", state);

        Assert.Equal(expectedPath, relativePath.Replace('\\', '/'));
    }

    [Fact]
    public void OwlAssetManifest_UsesModsAssetFolderBeforeLooseRepoAssetFolder()
    {
        var manifest = CreateAssetManifest();
        var candidates = InvokeStringArrayMethod(manifest, "BuildCandidatePaths", @"D:\Game\STS2\mods");

        Assert.Equal(@"D:\Game\STS2\mods\STS2_MCP.assets\pet\owl\talking.png", candidates[0]);
        Assert.Equal(@"D:\Game\STS2\mods\pet\owl\talking.png", candidates[1]);
    }

    [Theory]
    [InlineData(92, 92, 92, 255, false)]
    [InlineData(110, 108, 104, 255, false)]
    [InlineData(84, 126, 219, 255, true)]
    [InlineData(234, 188, 70, 255, true)]
    [InlineData(92, 92, 92, 0, false)]
    public void OwlAssetSanitizer_DetectsColoredSpriteAnchors_AndRejectsNeutralCheckerboard(
        byte red,
        byte green,
        byte blue,
        byte alpha,
        bool expectedAnchor)
    {
        var sanitizer = CreateAssetSanitizerType();
        var method = sanitizer.GetMethod("IsLikelySpriteAnchor", BindingFlags.Public | BindingFlags.Static);

        Assert.NotNull(method);
        var result = Assert.IsType<bool>(method!.Invoke(null, new object[] { red, green, blue, alpha }));
        Assert.Equal(expectedAnchor, result);
    }

    [Fact]
    public void OwlAssetSanitizer_GrowsAnchorMask_ToPreserveOutlineNearColoredPixels()
    {
        var sanitizer = CreateAssetSanitizerType();
        var method = sanitizer.GetMethod("ExpandMask", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(method);

        var seed = new bool[5, 5];
        seed[2, 2] = true;

        var expanded = Assert.IsType<bool[,]>(method!.Invoke(null, new object[] { seed, 1 }));

        Assert.True(expanded[2, 2]);
        Assert.True(expanded[1, 1]);
        Assert.True(expanded[2, 1]);
        Assert.True(expanded[3, 3]);
        Assert.False(expanded[0, 0]);
        Assert.False(expanded[4, 4]);
    }

    private static object CreateOwlSpec(PetVisualState state)
    {
        var type = typeof(PetOverlayViewModel).Assembly.GetType("STS2_MCP.PetOwlVisualSpec");
        Assert.NotNull(type);

        var factory = type!.GetMethod("FromState", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(factory);

        var result = factory!.Invoke(null, new object[] { state });
        Assert.NotNull(result);
        return result!;
    }

    private static object CreateAssetManifest()
    {
        var type = typeof(PetOverlayViewModel).Assembly.GetType("STS2_MCP.PetOwlAssetManifest");
        Assert.NotNull(type);

        var property = type!.GetProperty("Default", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(property);

        var result = property!.GetValue(null);
        Assert.NotNull(result);
        return result!;
    }

    private static object CreateRenderRecipe(PetVisualState state)
    {
        var type = typeof(PetOverlayViewModel).Assembly.GetType("STS2_MCP.PetOwlRenderRecipe");
        Assert.NotNull(type);

        var factory = type!.GetMethod("FromState", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(factory);

        var result = factory!.Invoke(null, new object[] { state });
        Assert.NotNull(result);
        return result!;
    }

    private static Type CreateAssetSanitizerType()
    {
        var type = typeof(PetOverlayViewModel).Assembly.GetType("STS2_MCP.PetOwlAssetSanitizer");
        Assert.NotNull(type);
        return type!;
    }

    private static string ReadEnumName(object instance, string propertyName)
    {
        return ReadProperty(instance, propertyName)?.ToString() ?? string.Empty;
    }

    private static bool ReadBoolean(object instance, string propertyName)
    {
        return Assert.IsType<bool>(ReadProperty(instance, propertyName));
    }

    private static float ReadSingle(object instance, string propertyName)
    {
        return Assert.IsType<float>(ReadProperty(instance, propertyName));
    }

    private static int ReadInt32(object instance, string propertyName)
    {
        return Assert.IsType<int>(ReadProperty(instance, propertyName));
    }

    private static object? ReadProperty(object instance, string propertyName)
    {
        var property = instance.GetType().GetProperty(propertyName, BindingFlags.Public | BindingFlags.Instance);
        Assert.NotNull(property);
        return property!.GetValue(instance);
    }

    private static string InvokeStringMethod(object instance, string methodName, PetVisualState state)
    {
        var method = instance.GetType().GetMethod(methodName, BindingFlags.Public | BindingFlags.Instance);
        Assert.NotNull(method);
        return Assert.IsType<string>(method!.Invoke(instance, new object[] { state }));
    }

    private static string[] InvokeStringArrayMethod(object instance, string methodName, string baseDirectory)
    {
        var method = instance.GetType().GetMethod(methodName, BindingFlags.Public | BindingFlags.Instance);
        Assert.NotNull(method);
        return Assert.IsType<string[]>(method!.Invoke(instance, new object[] { baseDirectory, PetVisualState.Talking }));
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let protoc = protoc_bin_vendored::protoc_bin_path()?;
    // SAFETY: build scripts run single-threaded before any other code observes the env.
    unsafe {
        std::env::set_var("PROTOC", protoc);
    }

    tonic_prost_build::compile_protos("proto/cookies.proto")?;
    Ok(())
}

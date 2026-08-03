use buzz_ws_client::NostrWsConnection;
use nostr::Keys;
use std::time::Duration;
#[tokio::main]
async fn main() {
    let a: Vec<String> = std::env::args().collect();
    let keys = Keys::parse(&a[1]).expect("key");
    let chan = &a[2];
    let mut c = NostrWsConnection::connect_authenticated("ws://localhost:3000", &keys, None)
        .await.expect("connect+auth");
    println!("AUTHENTICATED as {}", keys.public_key());
    let req = serde_json::json!(["REQ", "spike", {"kinds":[9], "#h":[chan]}]);
    c.send_raw(&req).await.expect("send REQ");
    let deadline = tokio::time::Instant::now() + Duration::from_secs(40);
    while tokio::time::Instant::now() < deadline {
        match c.next_event(Duration::from_secs(6)).await {
            Ok(v) => {
                let s = format!("{v:?}");
                println!("STREAM: {}", s.chars().take(220).collect::<String>());
            }
            Err(e) => println!("(idle/err: {e})"),
        }
    }
}

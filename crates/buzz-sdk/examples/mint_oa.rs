use nostr::{Keys, PublicKey};
use std::str::FromStr;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let owner = Keys::parse(&a[1]).expect("owner key");
    let agent = PublicKey::from_str(&a[2]).expect("agent pubkey");
    let cond = a.get(3).cloned().unwrap_or_default();
    println!("{}", buzz_sdk::nip_oa::compute_auth_tag(&owner, &agent, &cond).expect("mint"));
}

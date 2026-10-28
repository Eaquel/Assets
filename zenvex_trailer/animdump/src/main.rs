//! stdin: [{"anim":4,"t":0.1,"period":0.7,"weapon":"blood_scythe"}, ...]  → stdout: her kare için kemik ve silah dönüşümleri
use std::io::Read;
use zenvex_r3d::anim::{self, In, Style, Wk};
use zenvex_r3d::math::Xf;
use zenvex_r3d::model::Model;
use zenvex_r3d::rig::Skeleton;

fn xf(x: &Xf) -> serde_json::Value {
    serde_json::json!({"r": x.r.m, "t": [x.t.x, x.t.y, x.t.z]})
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dir = std::path::Path::new(&args[1]);
    let ch = &args[2];
    let m = Model::parse(&std::fs::read(dir.join(format!("{ch}.zxm"))).unwrap()).unwrap();
    let sk = Skeleton::of(&m);
    let mut s = String::new();
    std::io::stdin().read_to_string(&mut s).unwrap();
    let spec: Vec<serde_json::Value> = serde_json::from_str(&s).unwrap();
    let mut out = Vec::new();
    for f in spec {
        let wname = f["weapon"].as_str().unwrap_or("");
        let wk = if wname.is_empty() { Wk::None } else { Wk::from_model(wname) };
        let mut inp = In::new(f["anim"].as_u64().unwrap() as u8, f["t"].as_f64().unwrap() as f32, f["period"].as_f64().unwrap_or(1.0) as f32, wk, Style::of(ch));
        if !wname.is_empty() {
            let wm = Model::parse(&std::fs::read(dir.join(format!("{wname}.zxm"))).unwrap()).unwrap();
            inp.wback = -wm.meta.back;
        }
        let o = anim::evaluate(&sk, &inp);
        out.push(serde_json::json!({
            "bones": o.world.iter().map(xf).collect::<Vec<_>>(),
            "weapon": o.weapon.as_ref().map(xf),
            "trail": o.trail,
        }));
    }
    println!("{}", serde_json::Value::Array(out));
}

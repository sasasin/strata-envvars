# `strata --peer-device`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査時の `git status --short --branch` は `## main...origin/main`（clean）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの root） |
| オプション | `--peer-device` |
| 別名 | なし |
| 値 | 整数の GPU device index。1 以上で peer GPU を有効化する |

## 役割

2 枚目の GPU を adaptive expert-cache tier として使います。主 GPU に載らなかった、expert profile で順位付けされた expert を peer 側 VRAM に追加配置し、推論時に peer でも expert row を計算します。dense weights、KV cache、主 GPU の cache は peer に移しません（`include/strata/core/peer_experts.hpp:3-15`）。

## 使い方

```sh
strata --native /path/to/model.gguf \
  --expert-profile /path/to/profile.bin --expert-cache 4096 --peer-device 1
```

`--peer-device` は値を必須とし、使用には `--expert-profile` と正数の `--expert-cache` も必要です（`src/program/generate.cpp:1222-1224,8413-8416`）。

## 値と既定値

- 既定値は `-1`（無効）です。実装は値が `>= 1` の場合だけ peer tier を開きます。したがって `0` と負数は peer を有効化しません（`src/program/generate.cpp:751-760,8413`）。
- 値は `std::atoi` で整数化されます。厳密な数値形式や正の範囲を parser で検証する処理はありません。数値に変換できない文字列は `atoi` の結果 0 となり、peer は起動しません（`src/program/generate.cpp:3633`）。値を省略すると `--peer-device needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:3295-3297`）。
- 同じ option を複数回指定したときは parser が順に代入するため、最後に指定した値が使われます（`src/program/generate.cpp:3293-3297,3633`）。
- 有効値は実行時に見える device のうち 1 以上かつ device 数未満でなければなりません（`src/core/peer_experts.cpp:129-135`）。
- `0` は peer tier を有効化しませんが、既定値 `-1` と異なり、KVA の適用条件では「peer device 指定あり」と判定され、明示的に有効化した KVA を無効にします（`src/program/generate.cpp:6712-6717`）。

## 実行時の動作

値が 1 以上なら、エンジンは起動前に peer 用 mapped host buffer を portable 扱いに設定し（`src/program/generate.cpp:3849`）、expert cache の初期化後に peer tier を開きます。初期 cache には profile 順のうち主 cache にない expert を、peer GPU の空き VRAMから予約分を引いた予算内で格納します。開いた後は、peer GPU に格納した expert の推論も実行します（`src/program/generate.cpp:8411-8427`; `src/core/peer_experts.cpp:192-212,245-315`）。

peer の初期化が成功すると、stderr に peer GPU 番号、格納 expert 数と容量、初期化時間、および主 cache と合算した GPU 上の expert 数を出力します（`src/program/generate.cpp:8424-8427`）。

profile の上位部分は `STRATA_PEER_HOT`（既定 `0.45`）と `STRATA_PEER_HOT_AT`（既定 `8700`）でも配分され、指定割合の順位を peer 側に回してから両 cache を埋めます。値が `0 < f < 1` かつ対象順位が正のときに適用されます（`src/program/generate.cpp:5579-5607`）。推論中の適応処理では、主 cache と peer cache のどちらにもない高頻度 expert を peer cache に補充し、使用頻度の低い peer slot と入れ替えます（`src/program/generate.cpp:12639-12649`; `src/core/peer_experts.cpp:336-379`）。

## 適用条件と副作用

- `--expert-profile` が空、profile source が利用できない、または `--expert-cache <= 0` の場合、`strata generate: --peer-device needs --expert-profile and the expert cache` を stderr に出し、終了コード 1 で終了します（`src/program/generate.cpp:8413-8416`）。
- `--layer-split`、または `--expert-cache-device1..3` の remote expert cache と併用できません。該当時は競合する option 名を含むエラーを stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:4326-4332`）。
- `--adapt-async 1` と同時に指定した場合、peer 自体を拒否せず、非同期適応を無効化して blocking adaptive tier に切り替え、その理由を stderr に出します（`src/program/generate.cpp:9743-9746,9768-9784`）。
- 指定 device が見えない場合は `peer experts: CUDA device N is not visible ...` を返し、呼び出し側が stderr に出して終了コード 1 で終了します（`src/core/peer_experts.cpp:129-135`; `src/program/generate.cpp:8418-8422`）。peer 用に空きがない場合や主 cache にない expert が残っていない場合も初期化に失敗します（`src/core/peer_experts.cpp:192-210`）。
- peer tier は初期化時に VRAM を使って cache と作業領域を確保します。また、`--session-save` / `--session-load` による session file 処理は peer 有効時に拒否され、その要求について `session files do not support --peer-device` と応答します（`src/core/peer_experts.cpp:174-186`; `src/program/generate.cpp:14888-14895`）。
- prompt path でも peer が計算に参加しますが、P2P が使えない／利用を有効化できない場合は host 経由になります。peer access が有効でも往復コピーの検証に失敗した場合は警告を stderr に出し、host route に切り替えます（`src/core/peer_experts.cpp:141-164`; `src/program/generate.cpp:10747-10754`）。
- SYCL build の peer 実装は stub で、`PeerExperts::open` は「not ported to SYCL yet」として失敗します。有効な device 番号でも peer tier 初期化時に拒否され、呼び出し側は stderr に出して終了コード 1 で終了します（`sycl/src/core/peer_experts.cpp:19-23`; `src/program/generate.cpp:8418-8422`）。

## 根拠

- parser と値変換: `src/program/generate.cpp:3293-3298,3630-3637`
- 既定値とヘルプ記載: `src/program/generate.cpp:751-760,1222-1229`
- 競合検査: `src/program/generate.cpp:4326-4332`
- 必須条件、初期化、起動ログ: `src/program/generate.cpp:8411-8427`
- device 検査、P2P 判定、cache 予算・格納: `src/core/peer_experts.cpp:129-164,192-242`
- prompt path への接続と SYCL 制約: `src/program/generate.cpp:10747-10754`; `sycl/src/core/peer_experts.cpp:19-23`

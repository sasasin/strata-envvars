# `STRATA_KVA_SKIP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

KVA が近似する prompt chunk の late layer で、通常の state-only 処理から「attention half（GDN または QSA とその出力）を実行し、MoE half と expert transfer を省略する」処理へ切り替える。値を `moe` にしても KVA 自体は有効にならず、KVA が有効で当該 chunk・layer が近似対象になった場合にだけ差が出る。設定の読み取りは `strata::prefill::kva_config_from_env()`、処理の切り替えは `Prefill::run_impl()` にある（`engine/include/strata/prefill/kva.hpp:69-90,149-188`、`engine/src/prefill/prefill.cpp:4997-5007,5074-5082`）。

## 値と判定

`std::getenv("STRATA_KVA_SKIP")` の結果が null でなく、値全体が大文字小文字を区別して文字列 `moe` と等しい場合だけ `Skip::Moe` にする。数値変換や trim は行わない。環境変数が未設定、空文字、または `moe` 以外なら既定の `Skip::StateOnly` が残る。したがって `MOE`、`1`、`true`、`state`、`bogus`、`moe ` はいずれも state-only となる（`engine/include/strata/prefill/kva.hpp:69-75,88-90,182-182`）。

| 条件（build など） | unset | 有効になる値 | state-only のままになる値 |
|---|---|---|---|
| KVA の設定値判定 | `StateOnly` | 完全一致の `moe` | 空文字、`MOE`、`1`、`true`、`state`、`bogus`、`moe ` |

設定は `kva_config()` の関数内 `static const` に初回アクセス時の値を保存する。プロセス実行中に環境を変更しても、この設定済み config には反映されない（`engine/include/strata/prefill/kva.hpp:149-195`）。

## 有効になる条件

- `STRATA_KVA` も有効であること。KVA は `STRATA_KVA` が空でなく、先頭文字が `0` でない場合に on となる。`STRATA_KVA_SKIP` は KVA の on/off を切り替えない（`engine/include/strata/prefill/kva.hpp:77-78,152-156`）。
- state-only late-layer path を持つ build であること。`STRATA_GPU_METAL` build では `kKvaBackend` が false になり、KVA は無効化される。CUDA/HIP 側では true（`engine/include/strata/prefill/kva.hpp:43-49,152-156`）。
- KVA の全体適用条件を満たすこと。capture 中でなく、engine が block されず、prompt の開始位置が 0、全 trunk を読む（layer split なし）、画像なし、DFlash2 prompt taps なし、prompt 長が `STRATA_KVA_MIN_PROMPT` 以上かつ有効 suffix より 64 token を超えて長いこと。既定値は min prompt 4096、suffix 2048（`engine/include/strata/prefill/kva.hpp:85-87,95-96,104-133`）。
- 通常はモデル形状が 48 layers / 512 experts であること。異なる形状では KVA は辞退し、`STRATA_KVA_ANY_MODEL` が有効な場合のみ警告付きで許可される（`engine/src/prefill/prefill.cpp:4233-4244`）。
- multi-GPU layer split、`--batch` の batch slots、または `--peer-device` が使われると、generate 起動時に KVA がプロセス全体で block される。KVA が使われない限り、この変数による差もない（`engine/src/program/generate.cpp:8093-8114`）。
- 実際の切り替えは `kva_approx` な chunk かつ `l >= kva_split` の layer に限られる。`STRATA_KVA_ONLY` が `gdn` または `qsa` の場合は該当 layer 種別だけが対象。split は既定 36 で、1 から layer 数の範囲へ clamp される（`engine/src/prefill/prefill.cpp:4244-4246,4405-4412,4997-5005`; `engine/include/strata/prefill/kva.hpp:85,183-187`）。
- CLI に `STRATA_KVA_SKIP` 相当の引数・優先設定はなく、この値を読む箇所は環境からの読み取り一箇所。KVA を使わない通常の prefill はこの skip 分岐に入らない（`engine/include/strata/prefill/kva.hpp:182`; `engine/src/prefill/prefill.cpp:4997-5005`）。

## 実行時の詳細

KVA の適用判断後、各 chunk は末尾が exact suffix の開始位置より前にあるとき `kva_approx` になる。近似対象 layer では `kva_moe_only` が true となり、layer loop の half 0（attention）は通常どおり実行する。続く half 1 に入る直前に分岐し、その MoE 処理を飛ばして次の layer に進む。また、その layer の expert transfer を queue しない経路も `kva_moe_only` を使う（`engine/src/prefill/prefill.cpp:4405-4412,4680-4684,4997-5007,5074-5082`）。

`STRATA_KVA_SKIP=moe` は attention 出力を residual に反映する一方、近似対象位置の MoE 出力を計算しない。exact suffix や KVA が辞退した prompt は通常の計算経路であり、この変数は影響しない。CLI との優先順位で skip 値を上書きする処理はない。環境値は config の初回参照で一度だけ読み取られる（`engine/include/strata/prefill/kva.hpp:149-195`）。

## ログと測定値

KVA が実行された場合、prefill の診断行は `mode moe-skip` と表示する。KVA が有効でも適用されなかった場合は、明示的に KVA を on にしている経路などで辞退理由を stderr に出す。shape が未計測の場合の理由行、および起動時の backend / batch / split / peer-device 理由行はソースに定義されているが、これらは `STRATA_KVA_SKIP` 固有のログではない（`engine/src/prefill/prefill.cpp:8008-8044`; `engine/src/program/generate.cpp:8102-8113`）。

`docs/KVA.md:116` は `moe` で attention half を実行し、MoE half と expert transfer を省略すると説明しており、ソースの分岐と一致する。同文書にある速度・残差品質の評価は測定主張であり、本調査では再測定していない。`docs/DETAILS.md` にこの変数の記述は見つからなかった。

## 根拠

- 読み取り、既定値、完全一致判定、static cache: `engine/include/strata/prefill/kva.hpp:69-90,149-195`
- backend guard と KVA の適用条件: `engine/include/strata/prefill/kva.hpp:43-49,98-134`
- chunk / layer の適用、attention half 後の MoE skip: `engine/src/prefill/prefill.cpp:4233-4246,4405-4412,4997-5007,5074-5082`
- expert transfer の抑止と prefill log: `engine/src/prefill/prefill.cpp:4680-4684,8008-8044`
- engine 全体の block 条件と理由ログ: `engine/src/program/generate.cpp:8093-8114`

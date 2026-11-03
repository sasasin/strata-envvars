# `DS4_STREAM_ZC`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 の PCIe stream lane が使う、RAM にコピー済みの CPU lane expert を GPU から直接読めるように pin/map する設定です。該当 expert の decode pull は、通常の pinned staging への読み込みを経由せず、登録した RAM copy の行列アドレスを使います。これは stream lane の有効化そのものではありません。lane が無効ならこの値だけでは expert を stream しません。

## 値と判定

`zc_allowed()` は `std::getenv("DS4_STREAM_ZC")` の値をその場で `std::atoi()` に渡します。`atoi()` の結果が 0 なら明示 OFF、0 以外なら許可候補です。全体の文字列検証はなく、数値の後ろの文字は無視されます。

| 値 | `zc_allowed()` での扱い |
|---|---|
| 未設定 | `DS4_STREAM` が有効で、one-GPU path または `STRATA_DS4_PIN_BY_NEED` が許す場合に限り候補になる |
| 空文字 | `atoi("") == 0` となり OFF |
| 数値として 0 | OFF。例: `0`, `00`, `+0`, `-0` |
| 数値として 0 以外 | 許可候補。例: `1`, `-1`, `2` |
| 数字で始まらない値 | `atoi()` が 0 を返すため OFF。例: `true`, `false`, `abc` |
| 数字の後ろに文字がある値 | 数字の接頭辞で判定。例: `1abc` は許可候補、`0abc` は OFF |

先頭の空白と符号は `atoi()` の規則で解釈されます。値の範囲検査やエラー通知はありません。数値変換可能範囲を超える入力の結果は保証されません。

なお、後段の `one_gpu_plan()` は同じ名前を `env_tri()` に渡し、未設定または空文字を「未指定」として扱います。lane の較正で one-GPU path が不要と判定された場合、`ln_zc` が立っていて値が未設定/空なら登録済み copy を unregister して `ln_zc` を解除します。明示値がある場合はこの自動解除をしません。この helper も値が空でない場合は `atoi() != 0` かどうかだけを見るため、`abc` は明示 0 としてこの自動解除条件には入りません。

## 有効になる条件

- DS4 の GGUF 実行で、CPU lane の expert copy が作られている必要があります。`copy_experts()` は `--mmap-experts` が正の場合またはコピー対象が空の場合には何もせず、copy が完了した後に `copy_mode` を立てて `zc_pin()` を呼びます。
- `DS4_STREAM` または別名の `STRATA_DS4_STREAM` が必要です。両方未設定、または選ばれた値の `atoi()` が 0 なら `lane_env_off()` が true となり、この変数が非 0 でも pin しません。`DS4_STREAM` が設定されていると `STRATA_DS4_STREAM` より優先されます。`DS4_STREAM=2` は slot を保持する検証用設定で、lane は expert を stream しません。
- `DS4_STREAM_ZC` が未設定のときは one-GPU path が有効、または pin-by-need が有効でなければ許可されません。one-GPU path の自動判定は HIP build では行われず、非 HIP build で NVIDIA の単一の離散 GPU が単独 group にある場合が対象です。`DS4_STREAM=0` と、lane calibration が `off` で `DS4_STREAM_FORCE` も未設定の場合は自動 path が無効になります。
- 非 0 を明示すれば one-GPU path 外でも pin の候補になりますが、他の条件を迂回しません。GGUF であること、lane が有効であること、`zc_pin()` に RAM copy があること、`NH == 1` が必要です。device が登録 host pointer を直接扱えるか、pin-by-need と単一 device の組み合わせが必要です。integrated device を対象とする lane は拒否されます。
- PCIe lane 自体も GGUF かつ MoE token path で、`sync_decode` ではない場合に限り setup されます。対象 layer は trunk の単一 GPU layer で、MXFP4 format、非 MTP、`0 < k_exp <= kPicks`、expert blob が非空である必要があります。全 expert が VRAM に収まる layer や calibration が stream 不可の GPU では対象になりません。
- `STRATA_DS4_PIN_BY_NEED` は pin 方法にも関係します。これが有効なら routing profile の利用頻度順に chunk を pin し、最初の pin 失敗または `STRATA_DS4_PIN_GB` の上限で止めます。従って `DS4_STREAM_ZC=1` でも一部 copy だけが直接読める場合があります。

## 実行時の詳細

`one_gpu_path()` は device/group 構成と lane の既存 calibration を確認し、`ln_one` を初期化します。copy mode の `zc_pin()` は全 RAM chunk の登録を試みるか、pin-by-need なら一部を登録します。登録できた chunk に対応する RAM slot に `zc_slot` を設定し、1 chunk 以上 pin できた場合に `ln_zc` を true にします。後続の `one_gpu_plan()` は lane setup 後、実際に stream する layer がない場合に既定 path を切り、値が未指定なら pin を解除します。

decode 時は `zc_ok()` が該当 expert の copy の有無を調べます。`lane_publish()` は該当する matrix address を pull descriptor の `mat` に書き、`lane_go()` が GPU の lane pull を開始します。直接読めない copy は `mat` が 0 のままなので通常の pinned staging 経路が使われます。値は static cache されず、`zc_pin()` と `one_gpu_plan()` の各呼び出し時に読み直されますが、pin 判定後の各 decode request では環境変数を読み直しません。

pin 全体の登録に失敗した場合は `ds4: PCIe lane: pinning the copied experts failed - streamed ones pass the staging (STRATA_DS4_PIN_BY_NEED=1 pins the ones it can)` を stderr に出し、staging 経路を使います。pin-by-need の場合、登録できた GB 数と所要時間を `ds4: PCIe lane: pin by need: ...` として stderr に出します。lane setup は `ds4: PCIe lane: ... layers ... stream ...` を出します。lane 自体の適用可否や性能判定はこの環境変数の値だけでは決まりません。

## 根拠

- `src/dsv41/ds4_model.cu:5834-5844,5999-6008,6044-6045`: GGUF CPU lane copy の条件、`copy_mode` 設定、copy 完了後の `zc_pin()` 呼び出し。
- `src/dsv41/ds4_model.cu:6048-6068,6071-6084,6086-6093`: copy を直接読む機能の説明、pin-by-need、host pointer 対応、helper の値判定。
- `src/dsv41/ds4_model.cu:6103-6138,6143-6174`: one-GPU path の条件、lane calibration 後の plan、値が未指定の場合の pin 解除。
- `src/dsv41/ds4_model.cu:6176-6187,6212-6279`: `DS4_STREAM_ZC` の直接読み取り、許可条件、pin の失敗時 fallback とログ。
- `src/dsv41/ds4_model.cu:9711-9724,9753-9757`: `DS4_STREAM` と `STRATA_DS4_STREAM` の優先順位、lane off 判定、および lane の適用条件。
- `src/dsv41/ds4_model.cu:9884-9899,10098`: pin 済み matrix address を pull descriptor に渡して GPU pull を開始する箇所。
- `docs/DETAILS.md:1457`: 旧版の性能記録に zero-copy の比較があるが、`DS4_STREAM_ZC` の値判定や現 commit での条件を記述した説明は見つからなかったため、性能値は本書に転記していません。

# `DS4_STREAM_WIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek 4.1 の decode で、複数 token をまとめて検証する window の CPU lane 側 expert も PCIe lane から GPU に stream するかを選びます。未設定なら、対応する one-GPU decode path が有効な場合に window streaming も有効になります。明示設定は `ln_win` の選択をその既定条件から独立させますが、環境変数だけで streaming が実行されるわけではありません。

## 値と判定

`env_tri()` は unset または空文字列を「未指定」(`-1`) とし、それ以外は `atoi()` の結果が 0 かどうかに変換します。文字列全体の検証や範囲検査はありません。

| 値 | 判定 | `ln_win` の初期値 |
|---|---|---|
| unset / 空文字 | 未指定 | `one_gpu_path()` が選んだ `one` |
| `atoi()` が 0 | 明示的に無効 | false |
| `atoi()` が 0 以外 | 明示的に有効 | true |

したがって `1`, `01`, `1tail`, `-1` は有効、`0`, `00`, `false`, `tail` は無効です。先頭の空白や符号などは `atoi()` の規則に従います。数値変換不能な文字列は 0 になります。コードは値域を別途制限しません。

## 有効になる条件

- `one_gpu_path()` は HIP でないビルドに限り、GPU が1台、group が1つ、その group の memory device が1つで、CUDA device property 上 integrated でない場合に `one=true` とします。さらに `DS4_STREAM=0` や、lane calibration file が過去にその GPU で lane streaming なし (`off`) と記録している場合（`DS4_STREAM_FORCE` が unset の場合）は `one` を false にします。HIP、複数 GPU/group、integrated GPU では既定は false です。
- unset/空文字の `DS4_STREAM_WIN` はこの `one` を既定値にします。明示値が 0 以外なら、上記 one-GPU 判定が false でも `ln_win=true` になります。
- その後の `one_gpu_plan()` は `one_auto` の場合に PCIe lane の計測結果を確認します。どの layer も stream しない場合、`DS4_STREAM=2` または `DS4_STREAM_FORCE` がない限り one-GPU path を終了します。このとき `DS4_STREAM_WIN` が unset/空なら `ln_win` も false に戻しますが、明示値なら保持します。
- 実際の window streaming にはさらに GGUF、MoE token path、非同期でない decode、CPU lane に回る expert と利用可能な lane/device/class 等が必要です。window 側の実装は `T <= kWin` の複数 token で lane を選び、GPU の fetch 経路は lead・単一 MoE layer group (`nm == 1`)・MXFP4 形式の場合に接続されます。lane の staging や GPU slot の割当てに失敗した場合は PCIe lane が利用できません。
- `DS4_STREAM_SLOTS` は別設定で window streaming の候補数を 0〜`pcie::kSlots` (16) に制限します。さらに lane の計測 (`LaneAB`) が未判定または無効の場合、window の `lane_take_win()` は新たな stream expert を選びません。

## 実行時の詳細

環境変数はモデル/lane のロード処理で `one_gpu_path()` により読み取られます。lane setup と calibration の後、`one_gpu_plan()` が必要に応じて同じ値を再読します。値はリクエストごとには読みませんし、`DS4_STREAM_WIN` 自体の static cache もありません。各読み取り時点で `getenv()` を呼びます。

`ln_win` が true なら lane allocation は最大16 slot を確保し、window の CPU lane picks を `lane_take_win()` に渡します。同関数は window 内の distinct expert を集め、RAM にある候補を優先して lane の時間見積もりと slot 上限に基づいて stream 数を決めます。stream 対象の picks は CPU lane 側のリストから外し、pull を公開して PCIe lane の読み取りを開始します。GPU 側は到着した expert を fetch して window の計画に加えます。判定条件を満たさない場合は stream 数が 0 になり、これらの picks は CPU lane のままです。

観測可能なログは GGUF の場合に出る `ds4: the one-GPU decode path ...` で、明示値なら `DS4_STREAM_WIN=1` または `DS4_STREAM_WIN=0` が付記されます。lane 計画が one-GPU path を終了した場合は `ds4: the one-GPU decode path: off - the PCIe lane's plan streams nothing on this GPU (its CPU lane is as fast or there is no lane); v1.1.27's path...` が出ます。window lane の読み取り失敗では一度だけ `ds4: PCIe lane: reading a streamed expert failed - that token went without it` と stderr に出し、その token は当該 expert なしで進みます。lane setup の mapping 失敗時には `ds4: PCIe lane off: ...` が出ます。環境変数の不正値だけを理由にした専用エラーや終了処理はありません。

## 根拠

- `src/dsv41/ds4_model.cu:6090-6093`: unset/空文字の扱いと `atoi()!=0` の変換。
- `src/dsv41/ds4_model.cu:2797,6104-6138`: `one_gpu_path()` の呼出し、platform/device 条件、`DS4_STREAM_WIN` の既定値と起動ログ。
- `src/dsv41/ds4_model.cu:3791-3793,6140-6174`: lane setup 後の再評価、stream がない場合の既定 path 終了と `ln_win` の扱い。
- `src/dsv41/ds4_model.cu:9753-9787,10013-10102,10456-10468`: lane の前提条件・slot 割当て、window expert 選択と pull 開始、setup 失敗ログ。
- `src/dsv41/ds4_model.cu:9531-9538,9763-9767,10060-10099,14198-14206`: window における lane 呼出し、slot 数、計測判定、GPU fetch 経路。
- `docs/envvars/000_envvers.md:418` に候補名があります。Strata 内の完全一致検索では、実読込は上記 `env_tri()` 呼出し2箇所で、他の一致はコメントまたはログ文字列でした。`docs/DETAILS.md` にこの変数の追加説明は見つかりませんでした。

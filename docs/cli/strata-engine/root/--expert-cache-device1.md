# `--expert-cache-device1`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（engine の root parser。実装・診断メッセージでは `strata generate` と表記） |
| オプション | `--expert-cache-device1` |
| 別名 | なし |
| 値 | 非負の expert slot 数 `N`、または `auto` |

## 役割

主 GPU の expert cache に収まらない expert を、最初の helper GPU の VRAM に追加キャッシュします。モデル全体を複数 GPU に分割する `--layer-split` とは異なり、主 GPU は通常どおりモデル本体を実行し、helper は補完的な expert cache として使われます。CUDA0 が主 GPU の標準構成では helper は CUDA1 です（`src/program/generate.cpp:550-562, 3056-3068`）。

## 使い方

```sh
strata --pack /path/to/model --expert-profile /path/to/profile.bin --expert-cache 4096 --expert-cache-device1 auto
```

実際のモデル実行には別途必要な engine 引数を指定してください。`--expert-cache-device1` は `N` または `auto` を次の引数として受け取ります。`--expert-cache-device1=auto` の等号形式は parser が認識しません（`src/program/generate.cpp:2416-2421, 2562-2567`）。

## 値と既定値

- 既定値は `0`（無効）です。値は `std::atoi` で整数化され、`auto` の場合は内部 slot 上限を `INT_MAX` とし、自動サイズ調整フラグを立てます（`src/program/generate.cpp:559-560, 2562-2567`）。
- `N > 0` は指定数を上限として helper cache を作ります。`auto` は順位付けされた候補から、helper GPU の空き VRAMを調べ、512 MiB の余裕を残して入る数を選びます（`src/core/remote_experts.cpp:153-169, 181-188`）。
- `0` は無効です。`N < 0` は共通の resource validation で拒否され、stderr に `invalid sampling or resource parameter` を出して終了コード 2 になります（`src/program/generate.cpp:3352-3359`）。
- 数値文字列の厳密な形式検証はありません。`atoi` の変換結果が使われるため、数値として読めない文字列は 0 になり無効扱いとなり、数値の後ろにある非数値部分は変換対象外です（`src/program/generate.cpp:2562-2567`）。同じフラグを複数回指定すると、parser が読むたび同じ設定値を上書きし、最後の値が残ります（`src/program/generate.cpp:2416-2421, 2562-2567`）。
- `--expert-cache-device2` を正数で使う場合は device1 も正数でなければならず、device3 も同様に device2 が必要です。欠けた連番は同じ validation error で終了コード 2 になります（`src/program/generate.cpp:3352-3359`）。

## 実行時の動作

helper cache の利用には、`--expert-profile`、主 GPU の `--expert-cache`（正数）、および CPU expert pool が必要です。profile が空、主 cache が無効、または `--no-pool` の場合は `remote experts need --expert-profile, a CUDA0 expert cache and the expert pool` を stderr に出し、終了コード 2 で停止します（`src/program/generate.cpp:6662-6671`）。

profile 順を元に主 cache が保持していない expert を選び、helper 側へ読み込みます。`auto` または複数 helper の場合は profile にない expert も補充候補として追加します（`src/program/generate.cpp:6672-6693`）。helper の設定は `--expert-cache-device1` が最初の helper slot 群に対応し、通常は CUDA1 に割り当てられます。`STRATA_PRIMARY_DEVICE` で主デバイスが 0 以外なら、主デバイスを除いた可視 GPU の順番が helper に対応します（`src/program/generate.cpp:3058-3068`）。layer split 併用時は split stage が使わない可視 GPU に割り当てられます（`src/program/generate.cpp:3128-3142`）。

初期化時に helper GPU の CUDA context と空き VRAM を確認し、cache を確保して選択 expert を埋め、先頭 slot を検証します。起動ログには helper GPU の追加 expert 数と GiB が stderr に表示されます（`src/program/generate.cpp:3533-3547, 5600-5609, 6736-6746`; `src/core/remote_experts.cpp:70-97, 135-204`）。通常の helper cache の結果行は pinned host rows を通って戻ります。`--remote-expert-opt` を併用すると追加の remote expert decode 最適化を接続しますが、この別オプションは `--serve` がないと拒否されます（`src/program/generate.cpp:3365-3367, 6662-6665, 6736-6746`）。

## 適用条件と副作用

- helper GPU が可視で、主 GPU と異なる必要があります。非表示 GPU、主 GPU 自身、CUDA context・VRAM 割当・cache fill の失敗は helper 初期化エラーとなり、stderr に理由を出して終了コード 1 で停止します（`src/core/remote_experts.cpp:70-97, 135-204`; `src/program/generate.cpp:6736-6743`）。
- `auto` は slot 数を空き VRAM に合わせ、512 MiB を残せない場合はそこで選択を止めます。明示数でも必要量と 512 MiB を合わせて空き VRAMに収まらなければ失敗します（`src/core/remote_experts.cpp:153-184`）。`auto` で一つも未割当 expert が収まらない場合もエラーです（`src/core/remote_experts.cpp:159-174`）。
- `--peer-device` はこの helper cache と同時に使えません。組み合わせると `--peer-device cannot be combined with --expert-cache-device1..3 ...` を stderr に出し、終了コード 2 になります（`src/program/generate.cpp:3369-3375`）。
- helper cache は GPU VRAM、CUDA context、stream、device/host staging buffer を確保し、expert weight を GPU に転送します。終了時には `RemoteExperts` が stream を同期し、cache、CUDA allocation、pinned host allocation、stream を解放します（`src/core/remote_experts.cpp:99-133, 181-215`）。

## 出力とエラー

parser に値が続かない場合は `<option> needs a value` を stderr に出し、終了コード 2 です（`src/program/generate.cpp:2418-2421`）。負数や device1〜3 の連番条件違反は共通 validation error で終了コード 2、profile・主 cache・pool の不足も終了コード 2 です。GPU の可視性や割当など初期化段階での失敗は具体的な `CUDA<n> experts: ...` エラーを stderr に出し、engine は終了コード 1 を返します（`src/program/generate.cpp:3352-3359, 6666-6671, 6741-6743`; `src/core/remote_experts.cpp:70-97, 135-204`）。

## 根拠

- parser 表示とオプション説明: `src/program/generate.cpp:999-1011`
- 設定値の既定値・受理: `src/program/generate.cpp:550-562, 2416-2421, 2562-2567`
- 数値・連番・peer device の validation: `src/program/generate.cpp:3352-3375`
- helper GPU の対応付け、profile 候補・helper cache の構築: `src/program/generate.cpp:3056-3068, 6662-6747`
- GPU 検査、空き VRAM、auto sizing、cache fill と失敗: `src/core/remote_experts.cpp:70-97, 135-204`
- cache 確保後の staging allocation: `src/core/remote_experts.cpp:181-215`

# `--resident-cpu-experts`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--resident-cpu-experts` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

GPU expert cache に入らない expert を、モデルファイルの mmap から通常の CPU RAM へ読み込み、resident copy として保持します。GPU cache が保持する expert はそのまま GPU 側に置かれ、prompt 処理で cache slot を一時的に借りる構成では、その領域の expert も可能な範囲で RAM copy に含めます。resident copy が使われる間、GPU cache にない expert の通常参照は copy から供給されます。

## 使い方

ネイティブエンジンの `generate` で、`--mmap-experts` と静的な expert profile を併せて指定します。パスは実際の pack と profile の場所に置き換えてください。

```sh
strata generate --pack ./model --tokens 1 --max-new 1 \
  --mmap-experts --expert-profile ./expert-profile.txt --resident-cpu-experts
```

## 値と既定値

- 値を取らない真偽フラグです。parser は指定時に `resident_cpu_experts` を `true` にし、同時に明示指定を記録します。既定値は `false` です。繰り返し指定しても同じフラグを再度 `true` にするだけです（`src/program/generate.cpp:538,545,2756`）。
- 値を付ける構文ではありません。別の未知引数は usage と `unknown argument` を出して終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。
- このフラグ単独では page-lock を要求しません。オプション構造体の `resident_pin` 初期値は `false` で、実際の copy 作成時にもその値が渡されます（`src/program/generate.cpp:542,8203-8205`）。

## 実行時の動作

parser はフラグを立てるだけで、`--mmap-experts` や profile を自動設定しません。引数解析後、`--mmap-experts` がない、または `--expert-profile` が空なら、stderr に要件を表示して終了コード `2` で終了します（`src/program/generate.cpp:2749,2754,2756,3044-3046`）。profile は起動時に読み込まれ、読み込みに失敗した場合はエラーを表示して終了コード `1` です（`src/program/generate.cpp:4414-4420`）。

条件を満たすと、GPU cache の全 slot が埋まり GPU が同期した後、profile 順の配置計画に従い cache complement を構築します。CPU RAM copy のサイズ計画には GPU cache にない expert が含まれ、prompt lend 領域も指定された slot から含められます（`src/core/expert_source.cpp:3463-3496,3631-3646`）。エンジンは `pin=false` と headroom、resident budget を helper に渡します（`src/program/generate.cpp:8203-8205`）。このオプションだけの場合、budget は既定で `0`、headroom は既定で 8 GiB です（`src/program/generate.cpp:543-549`）。

copy の割り当てを始めると stderr に容量と「pageable resident」と表示されます。処理成功時は resident RAM の容量、pageable / locked 状態、GPU cache の expert 数、adaptive swap の状態を stderr に出力します（`src/core/expert_source.cpp:3722-3725`; `src/program/generate.cpp:8264-8270`）。adaptive swap が有効な設定なら GPU cache と RAM copy の間で expert を交換します（`src/program/generate.cpp:8259-8269`）。

## 適用条件と副作用

- `--shared-expert-arena` と `--mmap-experts` は併用できません。両方が有効だと stderr に競合を表示して終了コード `2` です（`src/program/generate.cpp:3040-3042`）。
- resident copy が利用可能 RAM / commit と headroom を超える場合、または copy のメモリ確保に失敗した場合、このフラグだけでは plain mmap への soft fallback を有効にしていません。resident 構築失敗を stderr に表示して終了コード `1` になります（`src/core/expert_source.cpp:3603-3629,3834-3840`; `src/program/generate.cpp:8271-8284`）。`--resident-experts` は別途 soft fallback を有効にするオプションです。
- `--resident-experts` は `--mmap-experts`、本オプション、page-lock、4 GiB headroom、soft fallback を設定します。一方、本オプション単独では page-lock は要求されず、headroom は 8 GiB です（`src/program/generate.cpp:536-544,2756-2765`）。
- `--resident-budget-gib N` も本オプションと mmap を有効にしますが、page-lock を要求し 4 GiB headroom を設定します。これは本オプションの単独指定と異なる予算付きの実行経路です（`src/program/generate.cpp:2767-2776`）。
- `STRATA_RESIDENT_PIN` と `STRATA_RESIDENT_HEADROOM_GIB` は `--resident-experts` / `--resident-budget-gib` の引数処理で読み込まれます。本オプション単独の parser 分岐では読まれません（`src/program/generate.cpp:2756-2776`）。
- Qwen3.6-35B-A3B family は `generate.cpp` の通常 parser に入る前に別実装へ dispatch されます。その実装には本オプションがありません。通常の token 実行では unknown option として usage を表示し終了コード `2`、`--serve` では未対応 option として stderr に警告して読み飛ばします（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3749,3782-3795`）。
- Windows build では resident copy 構築前に startup unbuffered 読み取りを試み、適用可否を stderr に出す経路があります（`src/program/generate.cpp:5741-5752`）。Linux 等の他 build における同じ切替条件は、この箇所からは確定できません。

## 出力とエラー

- 依存フラグ不足: 要件メッセージを stderr に出し、終了コード `2`（`src/program/generate.cpp:3044-3046`）。
- resident RAM の容量不足・確保失敗: helper が理由を返し、stderr に `CPU expert residency` のエラーを出して終了コード `1`（`src/core/expert_source.cpp:3613-3629,3834-3840`; `src/program/generate.cpp:8282-8284`）。
- 成功時: resident copy 作成量などを stderr に表示します（`src/core/expert_source.cpp:3722-3725`; `src/program/generate.cpp:8264-8270`）。

## 根拠

- parser、既定値、help 説明、関連する resident mode の設定: `src/program/generate.cpp:536-549,1066-1071,2749-2776`。
- family dispatch と Qwen3.6 parser の非対応動作: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3795`。
- 要件検証と static profile 読み込み: `src/program/generate.cpp:3040-3046,4414-4420`。
- resident copy 構築・失敗経路・成功時出力: `src/program/generate.cpp:8203-8284`; `src/core/expert_source.cpp:3457-3475,3600-3629,3722-3725,3834-3840`。
- prompt lend 領域と resident copy の配置: `src/core/expert_source.cpp:3631-3646`。

確認範囲は記載した Strata checkout のソースです。既存バイナリの `--help` や Release 配布物は照合していません。

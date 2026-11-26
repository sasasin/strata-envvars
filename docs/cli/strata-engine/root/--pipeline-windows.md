# `--pipeline-windows`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、`--serve` 時） |
| オプション | `--pipeline-windows` |
| 別名 | なし |
| 値 | 整数相当の値。parser は `atoi` で読み、0〜2 に丸める |

## 役割

レイヤー分割した複数 GPU 上で、単一リクエストの prompt 処理や decode の verify window を、各 stage が順番に処理する代わりに重ねて実行します。`1` は prompt の short-read window を重ね、`2` はそれに加えて decode window も投機的に重ねます。適用されない条件では値を 0 に戻し、通常の逐次経路で続行します。(`engine/src/program/generate.cpp:1145-1150, 6532-6537, 6584-6601`)

## 使い方

```sh
strata --serve --layer-split 24 --mtp ./draft --spec 4 --pipeline-windows 2
```

`--layer-split` などで GPU 間のレイヤー分割を構成した `--serve` 起動に指定します。上の例は引数の組み合わせを示すもので、モデルや GPU によって実行可能性は異なります。(`engine/src/program/generate.cpp:6584-6598`)

## 値と既定値

- `0`: 無効。stage は窓ごとに順番に処理します。
- `1`: prompt の short-read window だけを重ねます。2 stage の分割に限られます。
- `2`: prompt と decode の window を重ねます。decode 側は stage 0 が次の window を投機実行し、stage 1 が現在の window を検証し、予測が不一致なら先行側の状態を戻します。(`engine/src/program/generate.cpp:1145-1149`)
- 省略時の内部初期値は `-1` で、自動判定になります。自動で有効になる場合は値 `2` です。(`engine/src/program/generate.cpp:1150, 6560-6579`)

parser は `atoi` の結果を `max(0, min(2, value))` に通します。そのため負数は `0`、2 より大きい値は `2`、空値や数値として読めない文字列は `0` になります。複数回指定した場合は引数走査中に後の値が上書きします。値を省略すると `needs a value` を stderr に出して終了コード 2 で終了します。(`engine/src/program/generate.cpp:3842-3847, 4119`)

自動判定は `--serve`、GPU 間のレイヤー分割、別 GPU 上の各 stage などを前提とし、HIP build でのみ有効化されます。さらに `decode_defaults_arch_ok()` の GPU architecture 条件を満たす必要があります。既定の最小 stage 数は通常 3 で、MTP drafter を先頭 stage に置ける構成かつその配置が既定で選ばれる場合は 2 です。`STRATA_PIPELINE_AUTO_MIN_STAGES` を設定すると `atoi` 値を下限 2 で使い、`STRATA_PIPELINE_AUTO=0` は自動有効化を止めます。自動で有効になるには MTP と `--spec` 2 以上も必要です。(`engine/src/program/generate.cpp:6540-6546, 6560-6579`)

## 実行時の動作

正の値が設定されると、後続の `--serve` 初期化で各 stage に偶数・奇数 window 用の verifier を用意し、stage ごとの非同期 stream と parity ごとの hand-off を作成します。これにより stage 0 は次の window を処理しながら、後段は前の window を処理できます。値 `2` ではさらに各 front stage の GDN 状態 snapshot を使い、投機 decode の状態を復元できるようにします。(`engine/src/program/generate.cpp:13263-13288, 13725-13753`)

2 以上を指定したときは各 stage の GDN snapshot 用に追加 VRAM が必要です。pipeline 用 verifier 等の領域は expert cache の容量見積もりから差し引かれます。CUDA/HIP 経路では CUDA0 について予約量を stderr に表示します。(`engine/src/program/generate.cpp:6842-6850, 9052-9058`)

## 適用条件と副作用

正の値を指定しても、次の条件では stderr に理由を表示して `pipeline_windows=0` に戻し、起動は逐次経路で続きます: `--serve` でない、各 stage が別 GPU でない、GPU 間 layer split がない、値 `1` なのに 2 stage ではない、3 stage 以上で `--adapt-async` を使う、`--draft dflash2` を明示し `--draft-fallback mtp` を指定していない、MTP がないか `--spec` が 2 未満、`--batch`（後述の例外を除く）、`--peer-device`、helper expert cache を使う場合です。(`engine/src/program/generate.cpp:6584-6601`)

`--batch` との併用は通常 pipeline を無効にします。`STRATA_PW_WITH_BATCH=1` の場合は単独リクエスト用経路でだけ pipeline を維持し、batch window 自体は pipeline を使いません。自動判定は `STRATA_PIPELINE_AUTO=0` で止められます。(`engine/src/program/generate.cpp:6547-6559, 6602-6604`)

stream 作成、2つ目の verifier、hand-off、drafter row buffer の GPU/host allocation に失敗した場合、初期化は stderr に具体的な失敗理由を出して `return 1` します。値 `2` の GDN snapshot allocation だけが失敗した場合は警告を出し、decode を逐次実行に落として継続します。(`engine/src/program/generate.cpp:13276-13283, 13434-13483, 13725-13741`)

値 `2` の decode pipeline は repetition penalty 履歴や coupled draft sampling があるリクエストでは逐次化され、その理由は stderr に一度表示されます。(`engine/src/program/generate.cpp:21810-21819`)

この文書は CLI 索引が parser として指定する `engine/src/program/generate.cpp`（CUDA/HIP の `strata` エンジン経路）に基づきます。SYCL 側にも同名 parser がありますが自動既定条件が異なり、2枚の Battlemage GPU と MTP が条件です。この別実装は索引上の parser scope 外として、ここでは個別仕様を統合していません。(`engine/sycl/src/program/generate.cpp:760-765, 3590-3618`)

## 出力とエラー

自動有効時、または指定値が条件を満たさず無効化された時は stderr に状態または理由を表示します。pipeline 初期化が成功すると stage 数と decode の overlap 状態を stderr に出します。`--pipeline-windows` 自体に対応する独自の終了コードはなく、値の不足は共通 `next()` 処理による終了コード 2、stream/verifier/hand-off 等の初期化失敗は終了コード 1 です。(`engine/src/program/generate.cpp:3844-3846, 6575-6582, 6599-6601, 13283, 13442-13483, 13756-13760`)

## 根拠

- `engine/src/program/generate.cpp:1145-1150` — 値の意味と未指定時の初期値。
- `engine/src/program/generate.cpp:3842-3847, 4119` — 値取得、欠落値エラー、整数変換と範囲補正。
- `engine/src/program/generate.cpp:6540-6579` — 自動既定値、HIP 条件、MTP/spec、環境変数による制御。
- `engine/src/program/generate.cpp:6584-6617` — 適用条件、無効化と batch の例外。
- `engine/src/program/generate.cpp:6842-6850, 9052-9058` — VRAM 予約と cache 見積もり。
- `engine/src/program/generate.cpp:13263-13288, 13434-13487, 13725-13760` — verifier、stream、hand-off、snapshot の作成と初期化失敗。
- `engine/src/program/generate.cpp:21810-21825` — decode の逐次 fallback と実行経路。
- `engine/sycl/src/program/generate.cpp:760-765, 3590-3634` — scope 外の SYCL 実装における parser 初期値と自動条件の差。

# `--spec-follow`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの通常生成モード） |
| オプション | `--spec-follow` |
| 別名 | なし |
| 値 | token ID を並べたテキストファイルのパス |

## 役割

推測デコードのベンチマークや A/B 比較で、モデルの argmax ではなく指定ファイルの continuation を出力列として使います。draft がその列と一致したかを数えられるため、推測設定が異なる実行でも同じ token 列を処理できます。これは teacher-forced な診断であり、通常の sampling 挙動を測るものではありません。

## 使い方

```sh
# 通常生成モードで、prompt と continuation の token ID 列を指定して比較する
strata --native MODEL.gguf --tokens 1,2,3 --spec 4 \
  --expert-profile PROFILE.bin --spec-follow continuation.ids
```

`continuation.ids` は、たとえば `4, 5, 6` のように token ID をカンマまたは空白で区切って記述します。実際の model、prompt、推測デコードに必要な residency 構成に合わせて引数を指定してください。

## 値と既定値

- 値は次の引数をそのままパスとして受け取ります。値を省略すると parser は `--spec-follow needs a value` を stderr に出し、終了コード 2 で終了します。
- オプションを省略した場合の値は空文字列で、continuation を読み込みません。オプションを複数回指定すると parser は各値を同じフィールドへ代入するため、最後の指定が残ります。
- ファイルはカンマ、空白、タブ、改行などで区切った整数列です。各 ID は `0` 以上 `2147483647` 以下でなければならず、空ファイル・区切り文字だけの内容・不正な整数は受理されません。ID の個数に固定上限はコード上確認できません。

## 実行時の動作

- 通常の生成処理で `--spec` が 0 より大きく、prompt 後の推測ループへ入った場合にファイルを読みます。ファイルから得た列が空でない場合、生成上限は `min(--max-new, continuation の ID 数)` になります。
- 各 verify window で、モデルが出した argmax を continuation の対応する ID に置き換え、その置換後の列を draft acceptance の判定と commit に使います。出力された continuation のうち、argmax と異なる ID 数も集計します。ログに gated proposal が有効なら、stderr に「outputs before acceptance」を置換する teacher-forced 診断である旨を警告します。
- `--spec` が 0 の場合、推測ループに入らずファイルも読みません。`--serve` は別の永続 server 経路で、このオプションを参照しません（help も `--spec` と併用し `--serve` ではない用途と記載）。したがって `--serve` と一緒に指定しても server の要求出力には適用されません。
- 非空の continuation を使う推測ループには device residency table が必要です。ない場合は `--spec needs the device residency table` と stderr に出し、終了コード 2 で終了します。
- オプション自身は入力ファイルを読み込むだけで、指定先へ書き込みません。通常の生成出力に加え、完了時 stdout に continuation と argmax の不一致数を表示します。

## 出力とエラー

- ファイルを開けない場合、読み込みに失敗した場合、または ID 列が不正・空の場合は `strata generate: cannot read --spec-follow <path>` を stderr に出し、終了コード 2 で終了します。
- `--spec` の値が正でも推測ループへ到達しない（生成上限到達済み、既に EOS で終了など）場合、ファイル読み込み処理自体が実行されないことがあります。
- `--spec-follow` による入力処理以降のモデル・GPU・推測デコード処理の失敗は、通常の生成エラー経路に従います。

## 根拠

- `engine/src/program/generate.cpp:1030-1033` — オプションの目的と `spec_follow` の空文字列初期値。
- `engine/src/program/generate.cpp:1396-1398` — help の用途説明（continuation の出力、`--spec` と併用、`--serve` ではない）。
- `engine/src/program/generate.cpp:3842-3847,4051-4054` — 引数値の取得方法、値省略時の終了コード 2、parser 登録。型変換・追加 validation は parser では行わない。
- `engine/src/program/generate.cpp:1554-1581` — ファイルから読んだ token ID 列の区切り文字、整数形式、範囲、空列の検証。
- `engine/src/program/generate.cpp:24459-24489` — 推測ループ内でのファイル読み込み、失敗時の stderr と終了コード 2、continuation に応じた生成上限、residency table 要件。
- `engine/src/program/generate.cpp:12302-12308` — `--serve` の server 処理が別途実装される箇所。`spec_follow` の参照は通常生成の推測ループ内に限られる。
- `engine/src/program/generate.cpp:25160-25165,25205-25212,25261-25263` — argmax の置換、出力 token の差分計数と stdout 集計。
- `engine/src/program/generate.cpp:24842-24847` — gated proposal が有効な場合の teacher-forced 診断警告。
- `engine/sycl/src/program/generate.cpp:680,953-958,2047,13727-13737,14156-14157,14207,14245` — SYCL 実装にも同じ parser、用途、入力検証、置換、差分集計の実装があることを確認。

調査時の Strata checkout は `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。ビルド済み CLI の help は実行していません。通常生成経路での挙動は parser と実装を確認しましたが、個別 backend/build の実行結果までは確認していません。

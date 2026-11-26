# `strata --spec-oracle`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--spec-oracle` |
| 別名 | なし |
| 値 | 続く引数にトークン ID リストを含むテキストファイルのパス |

## 役割

投機的デコード時に、モデルのドラフトの代わりとして、ファイルに記録した期待継続トークンを検証ウィンドウへ入れる診断用オプションです。期待列に一致する継続では各行の受理を確認でき、`--spec` のウィンドウ幅を変えた比較などに使えます。単独では投機的デコードを有効にしません。

## 使い方

```sh
strata --model MODEL.gguf --tokens 1,2,3 --max-new 16 --spec 4 --spec-oracle expected.ids
```

`expected.ids` は現在の作業ディレクトリから読めるファイルの例です。ファイルに生成継続のトークン ID をカンマまたは空白区切りで記録します。

## 値と既定値

- パス値は次の引数から受け取り、オプション自体の既定値は空（指定なし）です。オプションを複数回指定した場合は、parser が同じ文字列フィールドへ順に代入するため最後の値が残ります（`engine/src/program/generate.cpp:4051`、`engine/sycl/src/program/generate.cpp:2045`）。
- ファイル全体を読み、トークン ID の区切りとしてカンマ、空白、タブ、改行などを受理します。各 ID は `[0, 2147483647]` の整数で、リストは空にできません（`engine/src/program/generate.cpp:1554-1580`）。
- `--spec` の既定値は通常 0（無効）で、Metal ビルドでは 2 です（`engine/src/program/generate.cpp:1010-1017`）。`--spec-oracle` のファイル読み込みは投機的ループに入った場合に行われるため、通常ビルドで `--spec` を有効にしない場合、このファイルは消費されません（`engine/src/program/generate.cpp:24464-24475`、`engine/sycl/src/program/generate.cpp:13709-13728`）。

## 実行時の動作

CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` の両 parser がこの値を `spec_oracle` に保存します。投機的ループでは指定パスを開いて全内容を読み、共通の整数リスト parser で解析します。ファイルを開けない場合、読み取りに失敗した場合、内容が空または不正な場合は `strata generate: cannot read --spec-oracle <path>` を stderr に出して終了コード 2 を返します（`engine/src/program/generate.cpp:24467-24476`、`engine/sycl/src/program/generate.cpp:13720-13729`）。

各検証ウィンドウで、接尾辞検索の候補がなく、MTP/DFlash2 などのドラフトも使わない行には、生成済みトークン数に対応する oracle の ID をドラフトとして使います。oracle の要素が尽きた位置には ID 0 を入れます。接尾辞検索候補、ドラフト、後続の lookup-chain 候補がある場合はそれぞれそちらが使われ、`--spec-corrupt` が有効なら oracle 由来の候補も変更され得ます（`engine/src/program/generate.cpp:25087-25094`、`engine/sycl/src/program/generate.cpp:14097-14104`）。したがって、指定ファイルはモデルの最終出力を固定する設定ではなく、検証対象となる候補列を供給します。

## 適用条件と副作用

- `--spec` が 0 の実行では投機的ループに入らず、指定パスは読み込まれません。投機的デコードには、モデルや実行経路に応じた他の要件もあります。たとえば verifier の初期化に必要なデバイス residency table がない場合は `--spec needs the device residency table ...` と stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:24480-24486`）。
- 指定ファイルを読み取りますが、このオプションによる書き込みは確認できません。oracle の ID がモデルの語彙範囲内かどうかを事前検証する処理は、確認した parser と読み込み箇所にはありません。
- 同じ parser で `--spec-oracle` と `--spec-follow` の両方を指定しても、後者の継続列は出力継続の制御に使われます。oracle はドラフト候補列として別に読み込まれます（`engine/src/program/generate.cpp:24473-24480`）。

## 出力とエラー

- 値を省略すると共通の引数取得処理が `<option> needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- ファイル読み込み・内容解析に失敗すると前述の `cannot read --spec-oracle` を stderr に出して終了コード 2 です。エラーメッセージではファイルを開けない場合と ID リスト不正を区別しません（`engine/src/program/generate.cpp:24467-24476`）。

## 根拠

- `engine/src/program/generate.cpp:1010-1028` — 値の保存先、spec の既定値、コメントにある oracle の用途。
- `engine/src/program/generate.cpp:1554-1580` — ID リストの区切り、整数範囲、空リスト拒否。
- `engine/src/program/generate.cpp:4050-4053`、`engine/sycl/src/program/generate.cpp:2044-2047` — CUDA/HIP 系と SYCL 系の parser 登録。
- `engine/src/program/generate.cpp:24467-24476`、`engine/sycl/src/program/generate.cpp:13720-13729` — ファイル読み込み、解析失敗時の出力と終了経路。
- `engine/src/program/generate.cpp:25087-25094`、`engine/sycl/src/program/generate.cpp:14097-14104` — oracle ID の検証ウィンドウへの代入と候補の優先関係。

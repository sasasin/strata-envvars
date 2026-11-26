# `--tokens-file`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--tokens-file` |
| 別名 | なし |
| 値 | トークン ID を記したファイルのパス |

## 役割

トークナイズ済みプロンプトをファイルから読み込み、`--tokens` で直接渡す場合と同じトークン列として推論エンジンに渡します。長い ID 列をコマンドライン引数に載せずに渡したい場合に使えます。parser はファイルを読み取って `Options::tokens` に格納し、後続の prefill がその配列を入力にします。

## 使い方

```sh
# prompt.ids にトークン ID を保存しておき、pack を使って生成する
strata generate --pack pack/full --tokens-file prompt.ids --max-new 128
```

ファイル内の例:

```text
248045, 123 456
```

## 値と既定値

- `PATH` は必須です。値を省略すると parser 共通の `--tokens-file needs a value` を stderr に出して終了コード 2 で終了します。
- ファイル内容は符号付き 32 bit 整数として解釈できる非負 ID（`0`〜`2147483647`）の列です。カンマまたは空白類（空白、タブ、改行、復帰、垂直タブ、フォームフィード）で区切れます。空のファイルや区切りだけのファイルは受理されません。
- 既定のファイルパスやトークン列はありません。`--tokens` と `--tokens-file` は同時に指定できず、どちらかのトークン入力を複数回指定すると `supply one token input only` を stderr に出して終了コード 2 になります。

## 実行時の動作

parser は指定されたパスを `std::ifstream` で開き、ファイル全体を文字列に読み込みます。開けない場合は `cannot open token file`、読み取り状態が失敗した場合は `cannot read token file` を stderr に出して終了コード 2 になります。内容に NUL バイトがある場合、数値列として解析できない場合、または列が空の場合は `malformed token file: ...` を stderr に出して終了コード 2 になります。

受理後の ID 列は `Options::tokens` に入り、prefill に渡され、プロンプト先頭の ID はデコード開始時のトークンとしても使われます。入力ファイル自体を書き換える処理はこのオプションの parser にはありません。通常の生成ではトークン入力が必要ですが、`--serve` でトークン入力を省略した場合はリクエスト用の既定値を別経路で設定します。`--tokens-file` を指定した場合はその入力が使われます。

プロンプト長は `--max-new` と合わせて `--max-context` に収まる必要があります。収まらない場合は `strata generate: --max-context ... cannot hold ...` を stderr に出し、終了コード 2 で拒否されます。このオプション単独ではモデル固有の ID 範囲までは検査せず、ここで確認した parser は共通の `int32` 非負範囲を検査します。

## 適用条件と副作用

このオプションは `strata-engine` の root 引数に属します。CUDA/HIP 系の `engine/src/program/generate.cpp` と SYCL 系の `engine/sycl/src/program/generate.cpp` の両 parser に実装されています。トークン列をファイルから読み込むため、プロンプトの長さがコマンドライン引数のサイズ制限に左右されにくくなります。読み込み時にファイル全体をメモリ上の文字列に置く実装ですが、ソース上にこの読み込みのサイズ上限はありません。

## 出力とエラー

このオプションの引数・ファイル・内容のエラーは stderr に出力され、終了コードは 2 です。ファイル読み込み後、prompt と生成長が context に収まらない場合も終了コード 2 です。prefill 自体が失敗した場合はエラーメッセージを stderr に出して終了コード 1 になります。

## 根拠

- `engine/src/program/generate.cpp:1210-1214` — usage と「カンマまたは空白区切りのトークン列」「`--tokens` の代替」という説明。
- `engine/src/program/generate.cpp:1554-1581` — 区切り文字、整数変換、非負 `int32` 範囲、空入力の検査。
- `engine/src/program/generate.cpp:3839-3869` — root parser、重複入力の拒否、ファイルの open/read、NUL・書式検査とエラー経路。
- `engine/src/program/generate.cpp:4996-5006` — 通常実行でトークン入力を要求し、serve で入力がない場合は別途既定値を設定する経路。
- `engine/src/program/generate.cpp:6152-6155` — prompt と生成長が context に収まるかの検査。
- `engine/src/program/generate.cpp:10714-10715, 24164-24166` — `Options::tokens` のプロンプト開始位置と prefill への入力利用、prefill 失敗時の出力と終了コード。
- `engine/sycl/src/program/generate.cpp:802-806, 1053-1070, 1890-1908, 2504-2514, 2636-2639, 3276-3279, 13385-13387` — SYCL parser と同等の受理・検査・実行経路。

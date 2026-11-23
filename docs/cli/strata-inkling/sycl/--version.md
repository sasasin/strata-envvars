# `--version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

SYCL 版 Inkling エンジンが組み込むバージョン文字列 `strata-inkling 0.1.66` を表示して終了します。モデルの指定や GPU 初期化をせずにバージョンを確認できます。

## 使い方

```sh
strata-inkling-sycl --version
```

## 値と既定値

値を取りません。別名、既定値、入力値の validation はありません。parser は `--version` を走査中に見つけると、その場で処理を終了します。したがって後続の引数は処理されず、先行するオプションの値として消費された `--version` はオプションとして認識されません（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`）。

## 実行時の動作

`main` の冒頭で初期化関数を呼び、その後の引数走査で `--version` を検出すると `strata-inkling 0.1.66` を stdout に出して終了コード 0 で戻ります（`engine/src/inkling2/sycl/ink_sy_main.cpp:101-115`）。この早期終了により、モデル未指定時の通常 usage 表示、モデルのロード、SYCL 実行処理には進みません（同 `:166-184`）。

## 適用条件と副作用

モデルファイルや GPU がなくても、parser まで実行できればバージョンを表示します。ただし `--version` 判定より前に `ensure_l0_v1_default()` が呼ばれ、環境変数 `UR_LOADER_USE_LEVEL_ZERO_V2` が未設定の場合は、そのプロセスの環境に値 `0` を設定します。すでに設定されている値は上書きしません（`engine/src/inkling2/sycl/ink_sy_main.cpp:101-115`、`engine/src/inkling2/sycl/ink_sy_common.h:46-52,63-69`）。ファイルやネットワークへの操作はこの経路では確認できません。

## 出力とエラー

成功時は stdout に `strata-inkling 0.1.66` を1行出力して終了コード 0 を返します（`engine/src/inkling2/sycl/ink_sy_main.cpp:115`）。この分岐自体にエラー経路はありません。通常のモデル未指定エラーは `--version` を検出せずに parser を抜けた場合の後続経路です（同 `:166-169`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-115` — 初期化、引数走査、固定バージョン文字列の出力と早期終了。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-184` — `--version` の早期終了後にだけ到達する通常のモデル指定確認・ロード。
- `engine/src/inkling2/sycl/ink_sy_common.h:46-52,63-69` — 環境変数設定の実装と既存値を保持する条件。
- `docs/cli/README.md:1572-1592` — `strata-inkling-sycl` の索引スコープと指定オプションのリンク。

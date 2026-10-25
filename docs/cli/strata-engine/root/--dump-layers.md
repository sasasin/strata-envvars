# `--dump-layers`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン引数） |
| オプション | `--dump-layers` |
| 別名 | なし |
| 値 | 出力ファイルのパス（`PATH`） |

## 役割

各処理位置について、入力残差と全レイヤー処理後の残差を float32 バイナリとして保存します。層ごとに推論結果を比較し、差異の発生位置を調べる診断用オプションです。ヘルプは「各位置について全レイヤー後の R を書く」と説明しています（`src/program/generate.cpp:881-886`）。

## 使い方

```sh
strata --native model.gguf --tokens 1,2,3 --dump-layers /tmp/layers.f32
```

`--native` と `--tokens` は通常の実行に必要な入力例です。CLI の入力形式の全体はこの文書の対象外です。

## 値と既定値

- 値は次の argv 要素から取得します。値を省略すると `--dump-layers needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2416-2421`）。
- parser は文字列をそのまま保存し、形式・存在確認・空文字の拒否・重複指定の拒否を行いません。複数指定時は後の値で上書きされます（`src/program/generate.cpp:2468-2472`）。
- 既定値は空文字で、指定しなければ dump は作成されません。空文字を明示した場合も空文字判定により出力処理は無効です（`src/program/generate.cpp:497`, `7091-7095`）。

## 実行時の動作

指定時、エンジンは `PATH` を `fopen(..., "wb")` で開きます。既存ファイルは切り詰められます。モデルの層数を `L`、`hc` をストリーム数、`n_embd` を埋め込み幅とすると、位置ごとに `(L+1) × hc × n_embd` 個の float を書きます。ヘッダーや位置番号はこの出力には付かず、位置ごとのレコードを連結します（`src/program/generate.cpp:7091-7095`, `15970-15972`, `16847-16852`）。

各レコードの slot 0 は layer 0 に入る入力残差、slot `l+1` は layer `l` の後の残差です。`session_loop` が device-to-host コピーを層ごとに enqueue し、ループ末尾の同期で完了させます（`include/strata/core/session.hpp:345-353`, `src/core/session.cpp:664-674`, `758-770`）。記録有効時は pinned host staging buffer が割り当てられ、各位置の処理後にその全体をファイルへ書きます（`src/program/generate.cpp:7091-7104`, `15946-15949`, `15970-15972`）。

ダンプ指定中は token graph のキャプチャ条件から外れ、通常の graph 経路で `session_loop` が呼ばれます（`src/program/generate.cpp:7406-7407`, `7471-7474`, `15938-15949`）。また fused GR の有効化条件からも除外されます（`src/program/generate.cpp:3930`）。

## 適用条件と副作用

- `--no-capture` と同時指定すると、`session_loop` が使われず staging buffer が埋まらないため、実行前に stderr へ理由を出し終了コード 2 で拒否します（`src/program/generate.cpp:6984-6986`）。
- 通常実装は CUDA の pinned host buffer と GPU からの層ごとのコピーを使います。SYCL 実装も同じ出力構造で、SYCL host allocation と queue memcpy を使います（`sycl/src/program/generate.cpp:5629-5648`, `sycl/src/core/session.cpp:893-905`, `1057-1070`）。
- `strata` が Qwen3.6-35B-A3B のモデルを検出すると、通常 parser の前に `src/qwen35` 実装へ引数ごと委譲します（`src/program/generate.cpp:2393-2407`）。`src/qwen35` 内ではこの option の parser・使用箇所を確認できなかったため、そのモデル経路での受理・動作は確認できません。別の診断用 `src/qwen35/q36ref.cu` にも同名フラグがありますが、これはエンジンの family 委譲先であることを示す根拠ではなく、本書の説明には含めません（同ファイル `:722-746`, `:790-805` は参考 CLI の実装）。

## 出力とエラー

- 出力先を開けない場合は `strata generate: cannot write PATH` を stderr に出し、終了コード 1 で終了します（`src/program/generate.cpp:7094-7098`）。
- pinned staging buffer を確保できない場合は stderr に失敗理由を出し、終了コード 1 です（`src/program/generate.cpp:7100-7104`）。
- `session_loop` 内の入力または各層のコピーが失敗するとエラー文字列を返し、呼び出し側が `strata generate: session_loop: ...` を stderr に出して終了コード 1 とします（`src/core/session.cpp:667-673`, `762-769`; `src/program/generate.cpp:15946-15949`）。
- 終了時にファイルを閉じ、出力先・次元を stdout に表示します。`fwrite` と `fclose` の戻り値はこの dump 経路では検査されていません（`src/program/generate.cpp:15970-15972`, `16847-16852`）。

## 根拠

- help 表示: `src/program/generate.cpp:881-886`
- parser と値取得: `src/program/generate.cpp:2416-2421`, `2468-2472`
- staging buffer とファイル open: `src/program/generate.cpp:7091-7104`
- session loop による各位置の記録: `src/program/generate.cpp:15938-15949`, `15970-15972`; `src/core/session.cpp:664-674`, `758-770`
- データ配置の契約: `include/strata/core/session.hpp:345-353`
- 通常・SYCL の実装差、および family 委譲: 本文の該当箇所を参照。

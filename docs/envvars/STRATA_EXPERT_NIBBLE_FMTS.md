# `STRATA_EXPERT_NIBBLE_FMTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

`STRATA_EXPERT_NIBBLE=1` で要求する 4-bit expert slot 機能について、変換対象にする gate/up の GGUF 形式 ID の集合を指定します。対象コードで変換可能なのは ggml type ID `22`（IQ2_S）、`18`（IQ3_XXS）、`21`（IQ3_S）だけです。未指定または空文字なら既定の順序 `[22, 18, 21]` を使います。この変数だけでは機能を有効にしません。

直接の環境読み取りは `include/strata/core/expert_nibble.hpp:250` の一箇所です。同ファイル `:216` の環境変数名は既定値のコメント、`src/program/generate.cpp:4172-4173` は対象形式がない場合の理由文字列、`docs/OLDER_GPUS.md:229` は設定例です。実際の読み取りはヘッダーの `config()` を通じ、generate 起動時に行われます。

## 値と判定

値はカンマ区切りの 10 進整数リストとして `strtoll(..., 10)` で一つずつ読みます。`include/strata/core/expert_nibble.hpp:221-235,250-260` の実装に基づく判定は次のとおりです。

| 値 | 結果 |
|---|---|
| 未設定、または空文字 | 既定リスト `[22, 18, 21]` のまま |
| 例 `22,18`、`+22, 18`、`22,` | 整数として読み取った ID のリストに置き換える。空白は各数値の前なら `strtoll` が読み飛ばす。末尾カンマは受理される |
| 数字に続く余分な文字、空要素（例 `x`、`22x`、`,22`、`22,,18`）、カンマ以外の区切り | リスト parse エラー |
| 認識対象外の整数 ID | `STRATA_EXPERT_NIBBLE_FMTS: type <ID> is not converted ...` エラー |

文字列全体の正規化や空白 trim はありません。末尾の空白は `strtoll` の次に残り、カンマでも終端でもない文字として parse エラーになります。負数も整数として parse された後、対応する 3 ID のどれでもないため無効です。ID の重複は除去されず、選択上は同じ形式を複数回指定しても対象が増えません。空文字以外で正常に parse できると既定リストを消去して指定リストに置き換えます。`strtoll` の `errno` や `int` への narrowing の範囲検査はありません。

parse エラーと未知 ID エラーは `Config.error` に保持されます（先に別の expert nibble 設定エラーがあれば最初のエラーを保持）。機能要求がない場合はこの FMTS エラーだけで `nib_asked` が真にならないため、形式リストは適用されず、FMTS エラー警告も出ません。`STRATA_EXPERT_NIBBLE=1` と併用した場合は起動前チェックでエラーとなり、警告のうえこの起動では 4-bit slot を使わず GGUF slot のまま続行します（後述）。

## 有効になる条件

- `STRATA_EXPERT_NIBBLE=1` が必要です。同スイッチは文字列全体が `1` のときだけ ON、`0` または未設定・空文字は OFF、その他の非空文字列は不正です（`include/strata/core/expert_nibble.hpp:242-246`）。FMTS には CLI の上書きはありません。
- 実装が組み込まれるのは CUDA、`STRATA_EXPERIMENTAL_SM60` 定義あり、HIP/Metal ではない build です（同 `:33-38`）。有効要求時は native experts が必要で、可視 CUDA device があり、全 device が compute capability 6.0 であることも起動前に確認します（`src/program/generate.cpp:2685-2706`）。
- 指定した形式の層でも、gate/up 形状が `2560 x 640` などの対象条件に一致し、skip 対象でなく、native pack に含まれる場合だけ変換されます。指定した全形式に対象層がなければ警告して通常 slot に戻ります（`include/strata/core/expert_nibble.hpp:315-340,343-356`; `src/program/generate.cpp:4167-4179`）。
- peer/remote expert cache、`--kv-grow`、`--vram-elastic`、`--expert-profile` 不在、`--expert-cache 0` などは起動前チェックで機能を拒否します。また prompt MMQ が変換 slot と両立しない場合も拒否理由になります（`src/program/generate.cpp:2682-2717`; `src/prefill/prefill.cpp:2642-2664`）。拒否はプロセス全体の起動失敗ではなく、この機能を無効にして GGUF slot で続ける警告経路です。

## 実行時の詳細

`config()` は関数内 `static const Config` として初回評価結果を cache します。generate は slot 推定・GPU allocation より前の `src/program/generate.cpp:4165-4175` で設定を参照し、値はそのプロセスで再読込されません。CLI option や別環境変数が FMTS のリストを上書きする処理はありません。

有効条件を通ると、各 layer の GGUF gate/up type が指定リストに含まれるかを調べ、対象 layer の VRAM slot を 4-bit layout として計画します。リストは gate/up 形式に適用され、down 部分は変換対象ではありません。変換を有効にした起動では adaptive tier の swap を無効化し、成功時に stderr へ変換 layer 数・形式別内訳・追加 VRAM 見積りを出します（`include/strata/core/expert_nibble.hpp:315-340`; `src/program/generate.cpp:4182-4199`）。形式リストに一致する layer がない場合の警告は `src/program/generate.cpp:4171-4179` にあります。

`docs/OLDER_GPUS.md:205-236` も GP100 向け `STRATA_EXPERT_NIBBLE=1` の条件と `STRATA_EXPERT_NIBBLE_FMTS=22,18,21` の形式選択例を記載しており、実装と整合します。同資料は個別の parser 境界値までは規定していません。

## 根拠

- 読み取り、既定値、parser、形式 ID 検証、layer 計画: `include/strata/core/expert_nibble.hpp:96-104,213-269,315-356`。
- build 条件: `include/strata/core/expert_nibble.hpp:33-38`。
- generate 起動時の要求判定、拒否、fallback 警告、成功ログ: `src/program/generate.cpp:2682-2719,4159-4200`。
- prompt 経路の適合チェック: `src/prefill/prefill.cpp:2642-2665`。
- 文書との照合: `docs/OLDER_GPUS.md:205-236`。

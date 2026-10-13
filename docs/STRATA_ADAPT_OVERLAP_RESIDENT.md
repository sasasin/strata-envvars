# `STRATA_ADAPT_OVERLAP_RESIDENT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の適応層で行う `STRATA_ADAPT_OVERLAP` のコピー重ね合わせを、resident RAM mode でも許可するための追加 opt-in です。この変数単独では overlap を有効にせず、通常の適応層や overlap の条件も満たす必要があります。resident RAM mode 以外ではこの変数の判定結果は使われません。

## 値と判定

`src.complement_ready()` が真のとき、環境変数が設定されており、値の先頭文字が `1` なら resident RAM mode に対する拒否理由を取り除きます。文字列全体や数値としての妥当性は検査しません。

| 値 | resident RAM mode での判定 |
|---|---|
| 未設定 | 無効（overlap を許可しない） |
| 空文字 | 無効（設定済みだが先頭文字が `\0`） |
| `1`, `10`, `1abc` | 有効（先頭文字だけを見る） |
| `0`, `true`, ` 1`, その他 `1` 以外で始まる値 | 無効 |

この変数の値は static cache されず、overlap gate の初期化時に直接 `getenv()` で調べられます。コード上、リクエストごとに再評価する処理ではありません。

## 有効になる条件

この opt-in が働くのは `src.complement_ready()` が真、つまり resident RAM mode が構築された経路に限られます。さらに次の条件も必要です。

- `STRATA_ADAPT_OVERLAP` 自体が有効。Linux CUDA は既定で有効（先頭文字が `0` の設定で無効）、Windows CUDA と HIP は先頭文字が `1` の場合だけ有効。
- `--adapt-every` と `--adapt-swaps` による適応層が有効。
- 単一 GPU で、layer split、`--peer-device`、`--remote-expert-opt` を使わない。
- `--adapt-async`、`--pipeline-windows`、page-locked swap source、`STRATA_DMA_BATCH` を使わない。
- `STRATA_ADAPT_LAG` が 1 で、`STRATA_ADAPT_NOWAIT` が有効でない。
- `STRATA_VERIFY_DEVICE_PLAN` による device-planned layers が無効。

これらの条件に合わない場合、この変数では overlap を強制できません。resident RAM mode 以外では本変数の値に関係なく resident mode のチェックを通過します。

## 実行時の詳細

overlap が有効なとき、次の decode window の開始時に pending swap の residency table を先に更新します。resident RAM mode では `soft_commit_exchanges()` で RAM copy 側の交換を予約し、コピーが届くまでの扱いを分けます。交換予約に失敗した場合は通常のコピー完了待ち `apply_pending(true)` に fallback し、overlap を行いません。

有効時の stderr ログは共通の `adaptive overlap ...` です。条件に合わない場合は、`STRATA_ADAPT_OVERLAP` が明示設定されているときに `STRATA_ADAPT_OVERLAP=1 is off: not in the resident RAM mode unless STRATA_ADAPT_OVERLAP_RESIDENT=1` などの理由が表示されます。resident opt-in 専用の成功ログはありません。

実装コメントには resident RAM mode での測定例として RTX A4000 +7.0%（5/5 pairs）と、46 GB RAM の環境の RTX 3060 -2.6%（0/5）が記されています。これはソースコメントに記録された個別結果であり、一般的な性能向上を示すものではありません。`docs/DETAILS.md` は通常の `STRATA_ADAPT_OVERLAP` の条件と測定を記載しますが、この resident 専用 opt-in の測定は記載していません。

## 根拠

- `src/program/generate.cpp:8272-8304` — overlap の条件判定、`STRATA_ADAPT_OVERLAP_RESIDENT` の先頭文字判定、失敗理由とログ。
- `src/program/generate.cpp:1330-1347` — 基本の `STRATA_ADAPT_OVERLAP` の既定値と platform ごとの値判定。
- `src/program/generate.cpp:11856-11875` — pending swap 適用時の resident RAM soft commit と通常待ちへの fallback。
- `src/program/generate.cpp:6600-6613,6765-6785` — resident RAM mode の説明、RAM copy と適応 swap の設定。
- `docs/DETAILS.md:1699-1706` — 基本の overlap 動作と通常モードの測定条件。resident opt-in 固有の記述はない。

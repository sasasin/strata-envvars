# `STRATA_PF_SMALL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

serve の自動 prefill chunk が小さい単一 CUDA カードの native pack で、prompt の fused expert 経路を止め、条件が合えば layer-major の読み方も選ぶ small expert cache 経路を許可します。`STRATA_PF_SMALL=0` はこの自動選択を止め、既定 prompt 経路を保ちます。これは独立した fused 設定ではなく、キャッシュから選んだ chunk に応じて serve 初期化時に行う選択です。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 自動選択を許可 |
| 空文字 | 自動選択を許可。設定有無ではなく先頭文字 `0` だけを検査する |
| 先頭文字が `0` | 自動選択を無効化（例: `0`, `0abc`） |
| その他 | 自動選択を許可（例: `1`, `false`, `off`, `2`） |

数値変換、文字列全体の比較、大文字小文字の判定はありません。CLI 引数や別変数で値を上書きする処理もありません。値が許可しても、下記の条件を満たさなければ経路は選ばれません。

## 有効になる条件

次の条件が必要です。

- `strata serve` の経路で、`--prefill auto` または `auto:N` により自動 chunk を使う。明示 chunk の `--prefill N` では `o.prefill_auto` が false なので対象外。
- prefill が expert cache を借りる設定である（expert profile があり、`--no-prefill-borrow` ではない）。cache から借りられないなどの理由でこの設定が後から解除された場合も対象外。
- 単一 GPU で、layer stage がない。
- 自動選択済み chunk が 1 以上で 8,192 未満。
- native pack で、`STRATA_DEFAULTS=026` の旧 defaults 経路ではない。
- CUDA build。HIP build は helper に `hip=true` を渡すため選択されない。
- `STRATA_PF_FUSED` が空でない値で設定されていない。空文字は「手動指定」として扱われず、自動選択を妨げない。

`STRATA_PREFILL_LAYER_MAJOR` に空でない値が設定されている場合、fused 経路は止められますが layer-major の自動選択は尊重されず、利用者の指定に任されます。空文字は未指定相当として扱われます。

## 実行時の詳細

serve の初期化で cache から既定 chunk を計算した後、`STRATA_PF_SMALL` をその場で読みます。値は static cache されず、この起動時の選択が終わった後に環境を変更しても、同じ serve 初期化には反映されません。

対象になると `small_card_prompt_path()` が fused-off を返します。実装はプロセス内の `pf_fused_override` を 0 にし、fused expert 経路を無効にします。layer-major の指定が利用者からなければ `STRATA_PREFILL_LAYER_MAJOR=1` も設定し、次の chunk scan をこの prompt layout 用にやり直します。chunk が取れた場合は stderr に `strata serve: small expert cache: ...` の行を出し、既定経路の chunk、選ばれた chunk、および関連変数を案内します。

再 scan で chunk が取れない場合は fused override を戻し、設定した layer-major 環境変数を解除して既定経路を再 scan します。その場合は stderr に `strata serve: small expert cache: the unfused prompt path does not fit here; the default path stays (chunk %lld tokens)` を出します。

## 根拠

- 候補名の全参照は `src/program/generate.cpp:10278-10279`（唯一の読み取り）と `src/program/generate.cpp:10278,10315-10316`（コメント・ログ文字列）。他の helper や動的な名前の参照は見つかりませんでした。
- serve の入口と auto chunk の CLI 判定は `src/program/generate.cpp:3451-3459,10054-10059`。borrow 条件は `src/program/generate.cpp:5644`、実際の cache scan は `src/program/generate.cpp:10186-10193`。
- 対象変数を読む条件、backend 判定、補助環境変数の判定と helper 呼び出しは `src/program/generate.cpp:10274-10290`。small-card helper の拒否条件と 8,192 境界は `include/strata/core/sm120_series.hpp:157-165`。`STRATA_DEFAULTS=026` の読み取りは `include/strata/core/defaults_026.hpp:26-29`。
- fused 経路の停止、layer-major 環境変数の設定、再 scan、失敗時の復元とログは `src/program/generate.cpp:10290-10319`。fused override が fused ring / native fused 経路に反映される箇所は `src/prefill/prefill.cpp:337-339` と `src/prefill/moe_fused_iq.cu:1998-2004`。
- layer-major 設定を使う箇所は `src/prefill/prefill.cpp:6295-6299,7705-7709`。

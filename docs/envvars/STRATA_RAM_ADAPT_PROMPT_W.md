# `STRATA_RAM_ADAPT_PROMPT_W`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の RAM 適応2（`STRATA_RAM_ADAPT2`）が、プロンプト中の expert routing を RAM 常駐コピーの次回入れ替え候補へ反映するときの重みを指定する。既定値は `0.25`。プロンプト中に観測した expert ごとの seed を decode の使用回数に加算して候補順位を作るため、値を上げるとプロンプトの routing が候補選定でより重く扱われる。routing、model weight、GPU tier の選択規則そのものはこの値で変更されない。値の読み取りは `--serve` ブロック内で行われるため、通常の `generate` 経路では参照されない（`engine/src/program/generate.cpp:12302-12348`, `16056-16067`, `22847-22917`）。

## 値と判定

serve 初期化時に `std::getenv` で設定有無を調べ、設定されていれば `std::atof` で数値変換し、`std::max(0.0, ...)` で負値を 0 にして `float` に格納する。未設定なら構造体の初期値 `0.25f` を使う。文字列全体の妥当性検査やエラー報告はない。`atof` が認識する先頭の数値部分が変換され、変換できない文字列は 0 になるため、たとえば `1junk` は 1、`0junk`・`junk`・空文字は 0。先頭空白は数値変換で読み飛ばされ、負値は 0 に丸められる。上限 clamp はなく、有限の正数はそのまま使われる。実際に seed を作るのは格納値が `> 0` の場合だけ。`nan` は通常の数値妥当性検査を受けず、`std::max(0.0, NaN)` の比較結果によりこの式では 0 側になる。一方、`inf` は正値として通り、有限性検査なしで seed 計算へ進む（`engine/src/program/generate.cpp:12334-12348`, `16059-16067`）。

| 条件 | unset | 有効になる値（例） | seed を作らない値（例） |
|---|---|---|---|
| `--serve` の初期化 | `0.25` | `0.25`, `1`, `1junk`, `2` | 空文字、`junk`、`0`, `0junk`, `-1`（いずれも格納後 `<= 0`） |
| `--serve` 以外 | この経路では読み取られず、値は適用されない | 該当なし | 該当なし |

正の値でも `STRATA_RAM_ADAPT2` が有効でなければ prompt callback を登録せず、seed は利用されない。`STRATA_RAM_ADAPT2` 自体は設定値を `atoi` し、非ゼロの場合に on になる（`engine/src/program/generate.cpp:12343-12348`, `16059-16067`）。

## 有効になる条件

- `--serve` で起動すること。この変数は serve 分岐内で一度読む。
- `STRATA_RAM_ADAPT2` が設定され、`atoi` の結果が非ゼロであること。未設定・空・数値として 0 の値では適応2が on にならない。
- prompt routing の seed を入れ替え判断に使うには、`STRATA_RAM_ADAPT` の整数値が 1 以上であること。これは1つの window で stage する上限にも使われる。
- RAM 入れ替え処理の window 条件を満たすこと: 初回 window ではない、decode usage が空でない、保留中の適応 round がない、非同期適応 job が idle（または存在しない）、RAM complement が ready、multi-GPU・peer・remote expert 経路ではない、`--batch 0`。条件に入らない window では prompt seed を使った promotion 処理は行われない（`engine/src/program/generate.cpp:22843-22849`）。
- Prompt callback が呼ばれる経路であること。prefill 実装は host 側に expert IDs をダウンロードした箇所で callback を呼び、GPU に IDs を保持する経路では呼ばないと説明している（`engine/src/prefill/prefill.cpp:5934-5941`, `engine/include/strata/prefill/prefill.hpp:265-267`）。

## 実行時の詳細

値は `--serve` 初期化時にローカルな `RamAdapt2` へ読み込まれ、その serve プロセスの間保持される。関数内 static cache ではないが、各 request/window で環境を読み直す箇所はないため、起動後に環境を変更しても反映されない（`engine/src/program/generate.cpp:12332-12349`）。CLI にこの重み用の上書き引数はなく、同ブロックの `STRATA_RAM_ADAPT_CACHED_W` など別変数の値もこの値を上書きしない。

`STRATA_RAM_ADAPT2` が on かつ重みが正なら、prompt 用 seed 配列をゼロ初期化し、prompt callback を登録する。callback は各 layer の host 側 routing ID ごとに `prompt_w * 20 * n_expert_used / n` を加算する（`n` は callback に渡された ID 数）。無効 ID は無視する。prefill 側は host に IDs を取得した後に callback を呼ぶ（`engine/src/program/generate.cpp:16059-16067`, `engine/src/prefill/prefill.cpp:5934-5941`）。

適応 window では seed を 5% 減衰させ、各 expert の decode usage に seed を足して RAM 非常駐候補を作る。`ue = usage + seed` が 2 以上の expert が候補となり、既存 RAM resident expert との見込みコスト差などで入れ替えを選ぶ。この経路は `ram_adapt_n` を上限として stage する。値が変えるのはこの RAM tier の候補順位であり、生成 token や GPU tier の選択ではない（`engine/src/program/generate.cpp:22847-22917`）。

## ログと測定値

この変数の読取値、変換失敗、clamp、seed 値を個別に出力するログはない。`STRATA_RAM_ADAPT2` が on の場合、request 後に `strata serve: resident RAM (STRATA_RAM_ADAPT2): ...` で I/O thread で読んだ promotion 数、install 数、skip 数の累積値を stderr に出すが、このログから prompt weight の値や寄与分は分からない（`engine/src/program/generate.cpp:23801-23805`）。対象変数固有の測定値はソースにない。

## 根拠

- `engine/src/program/generate.cpp:12332-12349` — `RamAdapt2` の初期値と環境変数の読み取り・変換。
- `engine/src/program/generate.cpp:16056-16067` — seed 配列の初期化と prompt routing の加算式。
- `engine/src/prefill/prefill.cpp:5934-5941`, `engine/include/strata/prefill/prefill.hpp:265-267` — host routing IDs に対する callback。
- `engine/src/program/generate.cpp:22843-22917` — 適応 window の条件と prompt seed を含む RAM 入れ替え候補計算。
- `engine/src/program/generate.cpp:23801-23805` — RAM 適応2の累積ログ。

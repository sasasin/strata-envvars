# `STRATA_PARK_TRACE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

会話状態の checkpoint 保存と `--serve` の conversation cache による park / restore の処理時間・K/V 保存内訳を stderr に出す診断用環境変数です。保存や復元方式を切り替えるものではなく、生成内容や保存データを変える分岐にも使われていません。`docs/DETAILS.md` も `STRATA_PARK_TRACE=1` を「park の joins と timers を stderr に出す診断」と記載しています（`docs/DETAILS.md:1504-1518`）。

## 値と判定

値の文字列や数値は parse されません。主な読み取りは `std::getenv(...) != nullptr` またはポインターの真偽値判定なので、値が存在すれば有効です。

| 設定 | 判定 |
|---|---|
| unset | 無効。trace 行を出さない |
| 空文字 (`STRATA_PARK_TRACE=`) | 有効。空文字でも `getenv` は非 null |
| 任意の非空文字列 | 有効。`1`、`0`、`false` も区別されない |

CLI 引数、設定ファイル、他の環境変数による優先順位や fallback はありません。関連する `STRATA_PARK_ASYNC` / `STRATA_PARK_VRAM_MIB` は park のコピー方式・VRAM slot を別途制御しますが、trace の有効性は切り替えません。

## 有効になる条件

- Conversation checkpoint の save が呼ばれたとき、join 待ち時間と checkpoint コピー時間のログが対象になります。これは `--serve` の conversation cache park に限らず、他の checkpoint save 呼び出しでも出るものです（`src/core/conversation_state.cpp:284-290, 386-390`; 呼び出し例 `src/program/generate.cpp:1915-1920`）。
- K/V 内訳と park / restore の VRAM slot 診断は conversation snapshot の save / restore 経路でのみ出ます。通常の `--serve` conversation cache は cache 容量・slot 数・prompt cache などの条件が満たされて park が実行されたときにこの経路へ進みます。保存を見送る条件（RAM admission や snapshot 容量など）が成立すれば、その park の内訳ログはありません（`src/program/generate.cpp:10635-10659,10677-10721`）。
- K/V slot の取得・復元ログはさらに `STRATA_PARK_VRAM_MIB` が正の値として読み取られている場合に限られます。`STRATA_PARK_ASYNC` が無効、または必要な K/V がない場合は slot 処理自体が始まらないことがあります（`src/core/conversation_snapshot.cpp:137-145,231-237,595-617`）。
- 候補名の参照・読み取りは CUDA 共通実装の `src/core/conversation_state.cpp` と `src/core/conversation_snapshot.cpp` にあります。`sycl/` 以下にはこの環境変数の読み取りがなく、Metal では checkpoint save が Metal engine へ早期委譲する経路があります（`src/core/conversation_state.cpp:291-294`）。本調査では Strata 側で確認できた範囲を記述し、HIP / Metal の内部動作は推測していません。

## 実行時の詳細

`checkpoint_save()` は `conversation_checkpoint_join()` の前後を計測し、環境変数がその時点で設定されていれば `strata parktrace: save join ... ms` を stderr に出します。この箇所だけは呼び出しごとに `getenv` を評価します。同関数内の vector resize、非同期 checkpoint の device-to-device copy、small copies の時間は、関数内 static の `atr` が初めて評価された時点の設定有無を使います（`src/core/conversation_state.cpp:284-305,321-339,363-381`）。

`conversation_snapshot_save()` は park の join、同期、checkpoint copy、live state save、K/V 保存の経過時間と K/V の大きさを集計し、`strata parktrace: joins ...` 行を stderr に出します。この経路の有効判定 `ptr` は関数内 static です。K/V save の pointer attribute 判定・resize・copy 時間も `park_trace_on()` の static 判定を使って集計します（`src/core/conversation_state.cpp:517-530,575-595`; `src/core/conversation_snapshot.cpp:249-256,351-377,590-597`）。

VRAM slot 診断では `STRATA_PARK_VRAM_MIB` が有効な場合に、slot の取得成功時は `strata parktrace: kv slot ...`、取得できなければ `strata parktrace: kv slot: none (...)`、restore 時は slot から復元した layer 数を stderr に出します（`src/core/conversation_snapshot.cpp:607-617,762-768`）。slot を取れない理由の記録には `off`、`budget`、`vram`、`cudaMalloc` などがあります（同 `:159-186`）。

各 static 判定はそれぞれの関数で初回に評価され、その後は同一プロセス内で再読込されません。一方、checkpoint join の直接判定は save ごとに読み直されます。したがって実行中の環境変更が可能な場合、ログ種別ごとに判定時点が異なります。環境変数は値の分岐にのみ使われ、CLI による上書き、trace に起因するエラー終了、失敗時 fallback は実装されていません。trace が無効でも本来の保存・復元処理は同じ経路で続きます。

## 根拠

- 全参照: `src/core/conversation_state.cpp:289,298,523`、`src/core/conversation_snapshot.cpp:145,254`。他の helper や動的な名前を介する `STRATA_PARK_TRACE` 読み取りは見つかりませんでした。
- checkpoint の保存とログ: `src/core/conversation_state.cpp:284-305,321-381`。
- park snapshot の集計とログ: `src/core/conversation_state.cpp:517-595`。
- K/V 内訳計測と slot のログ: `src/core/conversation_snapshot.cpp:249-256,351-377,590-617,762-768`。
- `--serve` の park 呼び出しと、park 結果のログ: `src/program/generate.cpp:10635-10721,10734-10746`。
- 文書での用途説明: `docs/DETAILS.md:1504-1518`。同資料に本変数の性能測定値はありません。

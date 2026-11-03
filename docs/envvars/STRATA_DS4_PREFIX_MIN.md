# `STRATA_DS4_PREFIX_MIN`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata-dsv41 --serve` が、複数リクエストで共有する prompt の開始部分（shared start）のモデル状態を RAM に別保存するときの、最小 token 数を決めます。閾値未満の開始部分は prefix cache に保存されず、後続リクエストはこの cache からその状態を再利用できません。通常の CLI 推論経路にはこの設定の読み取りがありません。

## 値と判定

`serve()` 内の `env_num` lambda は `std::getenv()` で取得した文字列を `std::atof()` に渡します。未設定の場合だけ既定値 `1024` です。設定値は変換後に `std::max(1.0, value)` で下限 1 を適用し、`size_t` にキャストします。

| 入力 | `prefix_min` の扱い |
|---|---|
| 未設定 | 1024 tokens |
| `0`、負値、または 1 未満の値 | 最小値 1 token に丸める |
| 正の数値 | 小数部を `size_t` への変換時に切り捨てる。例: `1024.9` は 1024 |
| 空文字、数値として始まらない文字列 | `atof()` が 0 を返すため 1 token |
| 数字の後ろに文字が続く値 | `atof()` が読めた数値部分を使う。例: `1024abc` は 1024 |

入力全体の妥当性検査、上限 clamp、無効値の警告やエラーはありません。`atof()` の結果が `size_t` で表現できる範囲を超える極端な値について、ソースに明示的な処理はありません。CLI 引数による上書きはありません。

根拠: `src/dsv41/ds4_main.cpp:560,804-806,824-828`。

## 有効になる条件

この値を読み取るのはサーバー処理の `serve()` だけです。実際に prefix が保存されるには、少なくとも次の条件が必要です。

- `m.marks_cap() > 0` であり、`STRATA_DS4_PREFIX_KEEP`（既定 2）が正数であること。`PREFIX_KEEP=0` なら `prefix_max` が 0 となり保存されません。
- リクエストに `shared=`、`pin=`、または shared として扱われる restore point があり、prompt の読み込みがその点まで到達すること。
- 共有開始部分が `prefix_min` tokens 以上であること。短い開始部分は `prefix_keep()` が保存前に除外します。
- 開始部分に画像が含まれないこと。保存状態は RAM 内に保持され、`STRATA_DS4_PREFIX_GB`（既定 2 GB）の budget を超える状態は追加されません。

`m.marks_cap()` は `STRATA_DS4_RESTORE_POINTS`（未設定時 4。別名 `DS4_RESTORE_POINTS`）で制御され、0 なら shared mark の利用を含む restore point が無効になります。prefix cache を保存・利用できない場合でも、処理は現在のモデル状態や通常の restore point を再利用できる経路を別に持ちます。`STRATA_DS4_PREFIX_STOP` は prefix 閾値以上の共有開始部分で読み込みを止める経路に関係しますが、`STRATA_DS4_PREFIX_MIN` 自体は開始位置の選択でなく、保存可能な長さの下限です。

根拠: `src/dsv41/ds4_main.cpp:804-806,824-842,1243-1249,1264-1268,1297-1304`; `src/dsv41/ds4_model.cu:7167-7173`。

## 実行時の詳細

`main()` がモデルをロードした後、`--serve` の場合に `serve()` を呼びます。閾値は `serve()` 開始時に一度、通常のローカル変数として読み込まれ、serve 中の各 request が同じ値を使います。値は `static` cache ではありませんが、serve の途中で環境を変更してもこの値には反映されません。別プロセスで起動し直すと再読込されます。子プロセスへの転送はこのコードにありません。

shared start は prompt の読み込み中、shared restore point で停止した状態を `m.slot_save()` で保存します。`prefix_min` 未満なら保存関数を呼びません。保存に失敗した場合は stderr に `ds4: keeping the shared start failed (...)` を出し、保存データが budget を超えた場合は追加せずログも出しません。保存成功時は token 数、保存サイズ、所要時間、保持数と合計サイズを stderr に出します。同じ prefix が既にある場合は LRU 使用時刻だけ更新します。上限を超えた場合は最も古く使われた prefix から削除します。後続リクエストで保存 prefix を戻せたときは stderr に `ds4: took back a ...-token shared start (...)`、復元に失敗した場合は読み直しに戻る旨を出して prefix を破棄します。

根拠: `src/dsv41/ds4_main.cpp:2621-2629,513,804-806,824-871`。

## 根拠

- 全参照検索で、環境変数名の実行時参照は `src/dsv41/ds4_main.cpp:806` のみ確認しました。同ファイル `:795` に既定値のコメントがあります。
- `src/dsv41/ds4_main.cpp:560` はこの場所の `env_num` 定義で、共通環境変数 helper ではなく `std::atof()` を用います。
- `src/dsv41/ds4_main.cpp:943` の CUDA 構成と `metal/CMakeLists.txt:139,183` の Metal 構成はいずれも `ds4_main.cpp` をビルド対象に含めます。ソース上の値判定に backend 別分岐はありません。
- `docs/DETAILS.md` にこの変数や shared prefix の追加説明は見つかりませんでした。

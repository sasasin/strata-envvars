# `STRATA_METAL_KEEP_HOST_WEIGHTS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンの expert streaming 時に、共有 host code が作った大きな device allocation（重みのコピーなど）を Metal runtime が purge して macOS に返す処理を抑止します。Metal window 自身はモデルファイルから expert を読むため、これらのコピーは通常の streaming window では使わないと実装コメントにあります。保持すると、その分のメモリを expert arena 用に空けない動作になります。

## 値と判定

`metal/src/engine/window.cpp` の `Window::stream_arena()` で `getenv()` を調べ、取得文字列が完全に `"1"` と一致するかを `std::string` で比較します。

| 値 | 動作 |
|---|---|
| 未設定 | purge を実行 |
| `1` | purge を省略し、host code の device allocation を保持 |
| 空文字、`0`、`01`、`true`、その他 | purge を実行 |

数値変換や先頭文字判定ではありません。大文字小文字を変換せず、完全一致です。

## 有効になる条件

`Window::init()` が `ExpertStream::wanted()` の結果を `stream_` に設定し、streaming が有効な場合に関係します。`stream_arena()` は streaming 中の arena がまだ ready でない場合に呼ばれます（window 実行、prompt 初期化経路）。streaming でない場合はこの判定・purge 処理に入りません。

`STRATA_METAL_KEEP_HOST_WEIGHTS=1` は arena を大きくしたり、purge 済みの allocation を復元したりする設定ではありません。単に `purge_device_allocations()` 呼び出しを飛ばします。`STRATA_METAL_ARENA_GB` など arena 予算に関係する別設定は、この環境変数の判定後も別途評価されます。

## 実行時の詳細

値が未設定または `"1"` 以外なら `purge_device_allocations(32u << 20)` を呼びます。この関数は device を同期した後、runtime の allocation 一覧から host allocation ではなく、既に purge 済みでもなく、32 MiB 以上の各 allocation を residency set から外し、purgeable-empty にして purge 済みとして記録します。返却した合計バイト数を `strata metal stream: %.2f GB of the host code's device weight copies given back (unused by the Metal window)` の形式で stderr に出します。条件未満の allocation と host allocation はこの処理の対象外です。

値が完全一致で `"1"` の場合は関数を呼ばず、この解放量ログも出しません。その後の arena 計画は通常どおり行われます。後から他の host code が purge 済み allocation に触れた場合、runtime は stderr に `STRATA_METAL_KEEP_HOST_WEIGHTS=1 keeps it` を含む診断と backtrace を出し、`abort()` します。この変数はその purge を避けるための設定です。

値は `stream_arena()` の呼び出しごとに読み直され、`static` cache には保存されません。ただし arena が ready になった後は初期化経路から同関数が再度呼ばれないため、初期化後に環境を変更しても、その arena に対する purge 判断はやり直されません。

## 文書との照合

`docs/MAC.md` は `STRATA_METAL_KEEP_HOST_WEIGHTS=1` を「Streaming」用スイッチとして挙げ、ホストコード自身の重みコピー（資料記載で 2–3 GB）を macOS に返さず保持すると説明しています。コードでは、この値は 32 MiB 以上の全非 host device allocation を対象とする purge 関数を抑止します。したがって 2–3 GB は資料の説明値であり、この値が常に同量の allocation を保持するという保証ではありません。

## 根拠

- `metal/src/engine/window.cpp:409-431` — Metal window 初期化と `ExpertStream::wanted()` による streaming 判定。
- `metal/src/engine/window.cpp:1016-1019,1127-1135` — streaming arena 初期化時の呼び出し、値の完全一致判定、stderr の解放量ログ。
- `metal/src/gpu/runtime.cpp:323-341` — purge 対象（非 host、未 purge、32 MiB 以上）、同期と purge の処理。
- `metal/src/gpu/runtime.cpp:187-194` — purge 済み allocation の参照を検出した場合の診断と abort。
- `docs/MAC.md:183-200` — streaming 向け設定の説明と 2–3 GB という記載。

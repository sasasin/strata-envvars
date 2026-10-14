# `STRATA_METAL_ARENA_CHUNK_GB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal backend の expert streaming arena を Metal buffer に分割するとき、各 buffer の目標上限（GiB）を指定します。arena 全体の予算や読み込む expert 数を直接決める変数ではありません。総 arena 予算は `STRATA_METAL_ARENA_GB` などから別途決まり、各 size class の slot を最大4個の buffer に配置します。

## 値と判定

`ExpertStream::make_arena()` が `std::getenv()` で値を読み、設定されていれば `std::atof(e) * 2^30` を `uint64_t` に変換して `want` にします。したがって単位は 10進 GB ではなく GiB（1024³ bytes）です。文字列全体の妥当性検証、範囲検証、clamp はありません。

| 値 | コード上の扱い |
|---|---|
| 未設定 | `max(8 GiB, total / 4 + 4 * biggest)` を目標値にする。`total` は配置する全 slot の byte 数、`biggest` は最大 slot サイズ。 |
| 数値文字列 | `atof` の変換値を GiB として byte 数にする。整数・小数を受け取り、小数 byte は `uint64_t` 変換で切り捨てられる。 |
| 空文字または数値に変換できない文字列 | `atof` の結果は 0 となり、明示的なゼロ相当として扱われる。 |
| 数値の後ろに文字が続く文字列 | `atof` が変換できる先頭の数値部分が使われる（例: `8GiB` は `8` 相当）。 |
| 負数、NaN、無限大、`uint64_t` の範囲外 | 拒否や安全な fallback を行うコードはない。範囲外の浮動小数点値から整数への変換結果は C++ で未定義となり得るため、挙動を保証できない。 |

変換後、実際の chunk 上限 `cmax` は `min(cx.max_buffer_length(), want)` を 16 KiB の `PAGE` 単位で切り下げた値です。値が未設定でない場合に「8 GiB 以上」などの最低値は適用されません。

## 有効になる条件

この読み取りは Metal backend の `ExpertStream::make_arena()` 内にあります。`Window::init()` が `ExpertStream::wanted()` の結果で stream 経路を選び、expert streaming が必要と判定された場合に `Window::stream_arena()` が arena を作ります。resident 経路ではこの変数は読み取られません。Metal engine のソースは `metal/CMakeLists.txt` で組み込まれます。

slot は size class 単位の連続配置で、次の slot が `cmax` を超えると次の buffer に移ります。ただし slot 自体は分割されないため、個々の slot が `cmax` より大きい場合にも、その slot を含む buffer は `cmax` を超え得ます。配置結果が4 buffer を超えると arena 作成は失敗し、エラー文字列 `metal stream: the arena needs more than 4 buffers (lower STRATA_METAL_ARENA_GB)` を返します。このエラーは arena 総量側の変数を案内しており、chunk 値を小さくしすぎた場合にも発生し得ます。

## 実行時の詳細

arena は最初の decode window または prompt で必要になった時に `Window::stream_arena()` から作られます。変数は static cache されず、`make_arena()` の呼び出しごとに読み直します。メモリ再確認による再試行が起きると再試行でも再読込します。arena 作成に成功した後は `st_->ready()` により同じ stream arena が再利用されるため、作成後にプロセス環境を変更しても既存 buffer 配置には反映されません。

この値に関する専用ログはありません。作成成功時の一般ログ `strata metal stream: expert arena ...; ...; %zu buffers` に実際の arena と buffer 数が出ます。4 buffer を超えたときは上記エラーが `err` に設定され、arena 初期化が失敗します。メモリ不足による再計画が発生する場合の再試行条件は `shrink_to()` の値で決まり、この変数はそれを直接変更しません。

## 根拠

- `metal/src/engine/stream.cpp:368-369,417-427`: arena の slot 集計、自動 `want`、環境変数の変換、Metal の最大長と 16 KiB 単位の丸め。
- `metal/src/engine/stream.cpp:433-444`: slot の chunk 配置と4 buffer 超過時のエラー。
- `metal/src/engine/stream.cpp:538-541`: 成功時に arena と buffer 数を出すログ。
- `metal/src/engine/window.cpp:425-432`: resident/stream の経路選択。
- `metal/src/engine/window.cpp:1016,1127-1128,1197-1209`: 初回 window での arena 作成と、メモリ再確認時の再試行。
- `metal/CMakeLists.txt:105-119`: `metal/src/engine/*.cpp` を Metal engine library に組み込む設定。

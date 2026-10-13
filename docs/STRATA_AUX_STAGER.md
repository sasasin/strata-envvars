# `STRATA_AUX_STAGER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

prefill の `Stager` が作るホスト側コピー用スレッドを、Linux の `--aux-cpus`（`STRATA_AUX_CPUS`）による補助 CPU 配置の対象にするかを選びます。`STRATA_AUX_STAGER` が `atoi` で 0 と判定されると、スレッドを補助 CPU 配置から除外します。それ以外の値または未設定では、通常の補助 CPU 配置処理に参加させます。

この変数は Stager のコピー処理やコピー対象を有効・無効にするものではなく、スレッド配置だけを変えます。Stager は prefill の初期化時に作られ、ストリーミング経路では主に pin できなかった expert のホスト側コピーを担当します。

## 値と判定

スレッド開始時、lambda 内の `static const bool` 初期化で一度 `getenv()` し、`std::atoi(v) == 0` を判定します。`atoi` は文字列全体の厳密な検証をせず、先頭の空白と符号の後の10進数部分を読み、数字の後ろの文字を無視します。数字が始まらない文字列は 0 になります。

| 値 | `keep` | Stager スレッドの処理 |
|---|---:|---|
| 未設定 | false | `pin_current_thread()` を呼ぶ |
| `0`, `00`, `0tail` | true | `note_owned_thread()` を呼び、補助 CPU の sweep 対象から除外 |
| 空文字、`abc`, `  ` | true | `atoi` が 0 を返すため、補助 CPU の sweep 対象から除外 |
| `1`, `-1`, `2tail` | false | `pin_current_thread()` を呼ぶ |

数値として 0 以外に変換される値はすべて `keep=false` です。整数型の範囲を超える文字列については `atoi` の結果に依存するため、確定した判定値は示せません。

## 有効になる条件

- `src/prefill/prefill.cpp` の Stager が作られる GPU prefill 経路で評価されます。Stager のスレッドは `Stager::init()` 内で作られます。
- Linux では `strata::aux_cpus` が実装されています。補助 CPU 配置が有効なとき、既定動作（未設定または非ゼロ値）は `pin_current_thread()` によりスレッドを補助 CPU 集合へ移します。補助 CPU 配置が無効ならこの関数は何もしません。
- `STRATA_AUX_STAGER=0` 相当の場合は `note_owned_thread()` がスレッド ID を owned として記録します。後でリクエスト単位で補助 CPU 配置を有効にして sweep しても、そのスレッドは移動対象になりません。
- Linux 以外では `aux_cpus.hpp` の同名関数が空実装なので、この環境変数を読んでもスレッド配置上の効果はありません。

## 実行時の詳細

Stager の各スレッドは生成直後に `keep` を確認し、真なら `note_owned_thread()`、偽なら `pin_current_thread()` を呼んでから `work()` に入ります。`keep` は関数内 static として共有されるため、プロセス内で最初の Stager スレッドが評価した値が以降も使われます。実行中に環境変数を変更しても再評価されません。別プロセスではそれぞれ最初の評価時の環境値が使われます。

補助 CPU 配置の `auto` は、補助スレッド用 CPU 集合を計画し、pool worker と host thread の CPU を避けます。通常動作では Stager スレッドもこの配置に参加します。一方 `STRATA_AUX_STAGER=0` にすると owned として扱われ、補助 CPU へ移されず、作成時に継承した配置に残ります。`docs/DETAILS.md` は、1つの spare CPU に最大32個の Stager スレッドを置くと、長い prompt の読み込みを遅くする場合があると説明しています。これは文書中の注意であり、この調査で性能を測定したものではありません。

この変数が出す専用ログやエラーは見つかりませんでした。一般の補助 CPU 設定に関する起動ログは `aux_cpus.hpp` 側で生成されます。

## 根拠

- `src/prefill/prefill.cpp:434-461`: Stager 初期化でスレッドを生成し、`STRATA_AUX_STAGER` を `std::atoi(v) == 0` で判定して配置関数を選択。
- `src/prefill/prefill.cpp:1091-1128`: prefill 初期化時に Stager を作成・初期化。
- `src/prefill/prefill.cpp:2316-2366,2375-2382`: ストリーミング時に Stager へ unpinned expert のコピー job を渡し、完了したホストバッファを GPU 転送に使う。
- `include/strata/platform/aux_cpus.hpp:18-19,234-260,274-285,344-357`: Linux 限定の配置機能、owned 登録、pin の挙動、非 Linux の空実装。
- `docs/DETAILS.md:1708-1726`: `--aux-cpus` の対象と `STRATA_AUX_STAGER=0` の説明、および多数の Stager スレッドが spare CPU を共有する場合の注意。
- `CMakeLists.txt:582-603`: `src/prefill/prefill.cpp` を `strata_prefill` に含め、`strata` 実行ファイルにリンクする構成。

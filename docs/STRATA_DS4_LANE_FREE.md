# `STRATA_DS4_LANE_FREE`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 専用エンジン `strata-dsv41` の CPU lane が使う CPU の一部を、decode kernel を起動して GPU を待つホストスレッドなどのために空けます。条件を満たす場合、既定では最初の NUMA pool の末尾から2 CPU を pool に割り当てずに残します。この変数で残す数を指定できます。

## 値と判定

値は `std::atoi` で整数に変換し、`std::max(0, ...)` で負数を0にします。整数として解釈できない文字列や空文字は `atoi` の結果が0になります。`atoi` は数値の後ろに続く文字を検査しないため、数値接頭辞がある文字列はその接頭辞の値として扱われます（例: `3x` は3）。変換可能な範囲を超える入力に対する `atoi` の結果は C ライブラリ上保証されません。

| 設定 | `lane_free` |
|---|---:|
| unset | 2 |
| `0`、空文字、数値で始まらない文字列 | 0 |
| 正の整数 | その整数 |
| 負の整数 | 0 |

値は `make_pools()` 内の関数ローカル `static const` として初回評価時に保存されます。プロセス内の最初の評価後に環境を書き換えても再評価されません。

## 有効になる条件

値が正でも、CPU を空ける処理が行われるのは、次の条件をすべて満たす場合だけです。

- CPU lane の最初の pool（`X == 0`）を作成中。
- `--cpu-threads` が指定されていないか、0以下（`o.cpu_threads <= 0`）。正数指定時はこの環境変数による縮小を行わず、CLI 指定から pool worker 数を決めます。
- `cs` に含まれる CPU 数が `max(1, std::thread::hardware_concurrency())` 以上で、CPU lane が全論理 CPU を取ると判定されている。
- ホストスレッド用の先頭 CPU を `c` から除いた後も、`c.size() > lane_free + 1` である。

その条件を満たすときだけ、`c` の末尾から `lane_free` 個を削除します。したがって、CPU lane が全論理 CPU を使わない構成、または先頭 CPU を除いた pool が小さい構成では、設定値にかかわらず追加の CPU は空けません。`lane_free=0` はこの追加削除を無効にします。

この変数が使われるのは、CMake の `STRATA_BUILD_DSV41` が有効で、かつ `STRATA_HIP_GFX906` が無効な構成で `strata-dsv41` をビルドした場合です。同オプションは既定 OFF です。通常の `strata` エンジンにはこの設定の読み取り箇所はありません。

## 実行時の詳細

モデル初期化中に `make_pools()` が呼ばれ、CPU lane 用 pool ごとに NUMA ノードの CPU リストを準備します。最初の pool では、その pool に割り当てる CPU リストの先頭（ホストスレッドの CPU）を除きます。上記条件を満たす場合、さらに末尾の `lane_free` 個を除外してから `Pool` を作ります。後続 pool にはこの環境変数を適用しません。設定変更に関する専用ログや警告はありませんが、モデル説明と verbose ログには CPU lane の thread 数が表示されます。worker 数を減らした結果はこの数に反映されます。

## 根拠

- `src/dsv41/ds4_model.cu:4619-4623,4626-4654`: CPU thread 数の集計、`make_pools()`、環境変数の読み取り、適用条件と CPU リストの縮小。
- `src/dsv41/ds4_model.cu:2620-2639`: CPU lane の core/NUMA pool 準備と、GGUF の場合は expert 配置後に pool を作る呼び出し順。
- `src/dsv41/ds4_model.cu:4408-4453,4657-4661,2778`; `src/dsv41/ds4_main.cpp:1295`: thread 数の表示。
- `CMakeLists.txt:797-811`: DSV41 エンジンの CMake オプションと実行ファイルの構成。`STRATA_BUILD_DSV41` は既定 OFF。
- `docs/DETAILS.md`: この変数についての記載や測定値は確認できなかったため、性能効果は断定しない。

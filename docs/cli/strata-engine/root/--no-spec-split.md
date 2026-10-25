# `--no-spec-split`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root） |
| オプション | `--no-spec-split` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

投機的検証ウィンドウの split を無効にします。split は有効な場合、2個以上の token を含む検証ウィンドウを2グループに分けて処理する設定です。通常の CUDA/HIP engine では split は既定で無効なので、このオプション単独では既定状態を変えません。`--spec-split` を同時に使う場合に、引数順に応じて split を無効へ戻せます。parser は `src/program/generate.cpp`、SYCL 側 parser は `sycl/src/program/generate.cpp` にあります（それぞれ 709, 2632–2634, 2734 行および 1929–1932, 2011 行）。

## 使い方

エンジンの通常の root 引数として指定します。

```sh
strata --pack ./pack --tokens "1,2,3" --spec 4 --no-spec-split
```

上例では `--spec-split` を指定していないため、`--no-spec-split` は既定の無効状態を明示するだけです。split を有効化する指定と併用する場合は、後に書いた値が残ります。

## 値と既定値

値は不要です。`Options::spec_split` は初期値 `false` です。parser は `--spec-split` で `true`、`--no-spec-split` で `false` を設定し、出現ごとに上書きするため、両方を指定した場合は最後の方が有効です。同じフラグを繰り返しても同じ値を再設定するだけです。独自の値 validation はありません（`src/program/generate.cpp:709, 2632, 2734`、SYCL parser: `sycl/src/program/generate.cpp:1929, 2011`）。

## 実行時の動作

エンジンは `spec_split` を verifier の `set_split` に渡します（layer split の stage verifier、pipeline 側 verifier、および通常 verifier: `src/program/generate.cpp:9212-9231, 16168-16170`）。CUDA verifier は split が有効で、検証対象 token 数 `T` が2以上、かつ batch recurrence でない場合に `G=2` とし、token 範囲を `(T + 1) / 2` の境界で二つに分けます。それ以外は `G=1` です（`include/strata/core/verify.hpp:338`、`src/core/verify.cpp:1122, 1141`）。SYCL verifier にも同じ `G` 判定があります（`sycl/src/core/verify.hpp:250`、`sycl/src/core/verify.cpp:831`）。

したがって、`--spec-split --no-spec-split` の順では無効、`--no-spec-split --spec-split` の順では有効になります。検証ウィンドウが実行されない場合、`T < 2` の場合、または batch recurrence の場合には、この設定による二分は行われません。

## 適用条件と副作用

この設定が使われるのは verifier の検証ウィンドウです。CPU/GPU の split 検証グループを作らない設定となります。parser と verifier のソース上、このフラグ自体がファイル、環境変数、ネットワーク、子プロセスを変更する処理は確認できません。分割による実行時間への効果は hardware、model、window に依存するため、ここでは一般化しません。

## 出力とエラー

このフラグ自体に専用の stdout/stderr 出力や validation error はありません。値を要求しないため単独で末尾に置けます。別の未知引数がある場合は parser が `unknown argument: ...` を stderr に出し、usage を表示して status 2 を返します（`src/program/generate.cpp:2418-2420, 2787-2792`）。

## 根拠

- parser の既定値と split/no-split 設定: `src/program/generate.cpp:709, 2632, 2734`。
- verifier への値の設定と適用条件: `include/strata/core/verify.hpp:336-338`、`src/program/generate.cpp:9212-9231, 16168-16170`、`src/core/verify.cpp:1122, 1141`。
- SYCL parser と適用条件: `sycl/src/program/generate.cpp:1929, 2011`、`sycl/include/strata/core/verify.hpp:250`、`sycl/src/core/verify.cpp:831`。
- 索引上の配置: `docs/cli/README.md:1128-1135, 1237`。索引は `strata-engine` の root parser 群に本オプションを掲載しています。

この調査では checkout 内の CUDA/HIP および SYCL ソースを確認しました。ビルド済み CLI の `--help`、Release artifact、実機上での性能差は確認していません。
